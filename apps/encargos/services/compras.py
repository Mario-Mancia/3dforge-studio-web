import uuid
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.catalogo.models import Producto
from apps.catalogo.services.catalogo import ErrorInventario, descontar_stock
from apps.core.calculos import calcular_linea, totales_documento
from apps.encargos.models import Encargo, EncargoDetalle, EstadoEncargo, HistorialEncargo

CLAVE_CARRITO = "carrito"
CLAVE_TOKEN = "compra_token"
CLAVE_ULTIMA = "compra_ultima"
MAX_POR_LINEA = 99
MAX_LINEAS = 30
VIGENCIA_TOKEN = 600


class ErrorCompra(Exception):
    pass


class CompraDuplicada(ErrorCompra):
    def __init__(self, encargo_id):
        super().__init__("La compra ya fue procesada.")
        self.encargo_id = encargo_id


class Carrito:
    def __init__(self, sesion):
        self.sesion = sesion
        crudo = sesion.get(CLAVE_CARRITO) or {}
        self._datos = {}
        for clave, cantidad in dict(crudo).items():
            try:
                if str(clave).isdigit() and int(cantidad) > 0:
                    self._datos[str(clave)] = min(int(cantidad), MAX_POR_LINEA)
            except (TypeError, ValueError):
                continue

    def _guardar(self):
        self.sesion[CLAVE_CARRITO] = dict(self._datos)
        self.sesion.modified = True

    @staticmethod
    def _cantidad(valor):
        try:
            cantidad = int(valor)
        except (TypeError, ValueError):
            raise ErrorCompra("La cantidad indicada no es válida.")
        if not 1 <= cantidad <= MAX_POR_LINEA:
            raise ErrorCompra(f"La cantidad debe estar entre 1 y {MAX_POR_LINEA}.")
        return cantidad

    @staticmethod
    def _producto(producto_id):
        try:
            producto = Producto.objects.filter(pk=int(producto_id), activo=True).first()
        except (TypeError, ValueError):
            producto = None
        if producto is None:
            raise ErrorCompra("El producto no está disponible.")
        return producto

    def _fijar(self, producto, total):
        if total > MAX_POR_LINEA:
            raise ErrorCompra(f"No puede comprar más de {MAX_POR_LINEA} unidades de un mismo producto.")
        if total > producto.stock:
            raise ErrorCompra(f"Solo hay {producto.stock} unidades disponibles de {producto.nombre}.")
        self._datos[str(producto.pk)] = total
        self._guardar()

    def agregar(self, producto_id, cantidad=1):
        cantidad = self._cantidad(cantidad)
        producto = self._producto(producto_id)
        if str(producto.pk) not in self._datos and len(self._datos) >= MAX_LINEAS:
            raise ErrorCompra("El carrito alcanzó el máximo de productos distintos.")
        self._fijar(producto, self._datos.get(str(producto.pk), 0) + cantidad)

    def actualizar(self, producto_id, cantidad):
        try:
            if int(cantidad) == 0:
                return self.quitar(producto_id)
        except (TypeError, ValueError):
            pass
        cantidad = self._cantidad(cantidad)
        if str(producto_id) not in self._datos:
            raise ErrorCompra("El producto no está en el carrito.")
        self._fijar(self._producto(producto_id), cantidad)

    def quitar(self, producto_id):
        self._datos.pop(str(producto_id), None)
        self._guardar()

    def vaciar(self):
        self._datos = {}
        self._guardar()

    def __len__(self):
        return len(self._datos)

    @property
    def unidades(self):
        return sum(self._datos.values())

    def lineas(self):
        productos = Producto.objects.in_bulk([int(clave) for clave in self._datos])
        resultado = []
        for clave, cantidad in self._datos.items():
            producto = productos.get(int(clave))
            disponible = bool(producto and producto.activo and producto.stock >= cantidad)
            calculo = calcular_linea(cantidad, producto.precio) if disponible else None
            resultado.append(
                {"producto": producto, "cantidad": cantidad, "disponible": disponible, "calculo": calculo}
            )
        return resultado

    def totales(self):
        return totales_documento([linea["calculo"] for linea in self.lineas() if linea["calculo"]])

    def hay_problemas(self):
        return any(not linea["disponible"] for linea in self.lineas())

    def items(self):
        return {int(clave): cantidad for clave, cantidad in self._datos.items()}


def iniciar_checkout(sesion):
    carrito = Carrito(sesion)
    if not len(carrito):
        raise ErrorCompra("Su carrito está vacío.")
    if carrito.hay_problemas():
        raise ErrorCompra("Algunos productos ya no están disponibles en la cantidad indicada. Revise su carrito.")
    token = uuid.uuid4().hex
    sesion[CLAVE_TOKEN] = token
    sesion.modified = True
    return token


@transaction.atomic
def _crear_encargo(cliente, usuario, items):
    productos = sorted(descontar_stock(items), key=lambda p: p.pk)
    calculos = [(p, items[p.pk], calcular_linea(items[p.pk], p.precio)) for p in productos]
    ahora = timezone.now()
    encargo = Encargo.objects.create(
        cliente=cliente,
        codigo=f"TMP-{uuid.uuid4().hex[:12].upper()}",
        descripcion="Compra de productos del catálogo",
        fecha_solicitud=ahora,
        estado=EstadoEncargo.PENDIENTE,
        **totales_documento([calculo for _, _, calculo in calculos]),
    )
    encargo.codigo = f"ENC-{ahora:%Y}-{encargo.pk:06d}"
    encargo.save(update_fields=["codigo"])
    for producto, cantidad, calculo in calculos:
        EncargoDetalle.objects.create(
            encargo=encargo,
            producto=producto,
            descripcion=f"{producto.nombre} ({producto.sku})",
            cantidad=Decimal(cantidad),
            precio_unitario=producto.precio,
            descuento=calculo["descuento"],
            impuesto=calculo["impuesto"],
            subtotal=calculo["subtotal"],
        )
    HistorialEncargo.objects.create(
        encargo=encargo,
        usuario=usuario,
        estado_anterior=None,
        estado_nuevo=EstadoEncargo.PENDIENTE,
        comentario="Compra confirmada desde la tienda.",
    )
    return encargo


def confirmar_compra(cliente, usuario, sesion, token):
    esperado = sesion.get(CLAVE_TOKEN)
    if not token or token != esperado:
        ultima = sesion.get(CLAVE_ULTIMA)
        if ultima:
            raise CompraDuplicada(ultima)
        raise ErrorCompra("La sesión de compra expiró. Revise su carrito e intente de nuevo.")
    if not cache.add(f"compra:{token}", 1, VIGENCIA_TOKEN):
        raise CompraDuplicada(sesion.get(CLAVE_ULTIMA))
    carrito = Carrito(sesion)
    items = carrito.items()
    if not items:
        cache.delete(f"compra:{token}")
        raise ErrorCompra("Su carrito está vacío.")
    try:
        encargo = _crear_encargo(cliente, usuario, items)
    except ErrorInventario as error:
        cache.delete(f"compra:{token}")
        raise ErrorCompra(str(error)) from error
    except Exception:
        cache.delete(f"compra:{token}")
        raise
    sesion.pop(CLAVE_TOKEN, None)
    sesion[CLAVE_ULTIMA] = encargo.pk
    carrito.vaciar()
    return encargo
