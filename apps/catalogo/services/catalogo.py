import uuid

from django.core.files.storage import default_storage
from django.db import transaction

from apps.catalogo.models import Producto


class ErrorInventario(Exception):
    pass


class StockInsuficiente(ErrorInventario):
    pass


class ProductoNoDisponible(ErrorInventario):
    pass


def _normalizar(items):
    normalizado = {}
    for producto_id, cantidad in dict(items).items():
        cantidad = int(cantidad)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser un entero positivo.")
        normalizado[int(producto_id)] = cantidad
    if not normalizado:
        raise ValueError("No se indicaron productos.")
    return normalizado


def _bloquear(ids):
    return {p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=ids).order_by("pk")}


def _guardar(producto):
    producto.save(update_fields=["stock", "actualizado_en"])


@transaction.atomic
def descontar_stock(items):
    items = _normalizar(items)
    productos = _bloquear(items)
    for producto_id in sorted(items):
        producto = productos.get(producto_id)
        if producto is None or not producto.activo:
            raise ProductoNoDisponible(f"El producto {producto_id} no está disponible.")
        if producto.stock < items[producto_id]:
            raise StockInsuficiente(f"Existencias insuficientes de {producto.nombre}.")
    for producto_id, cantidad in items.items():
        productos[producto_id].stock -= cantidad
        _guardar(productos[producto_id])
    return list(productos.values())


@transaction.atomic
def reponer_stock(items):
    items = _normalizar(items)
    productos = _bloquear(items)
    faltantes = set(items) - set(productos)
    if faltantes:
        raise ProductoNoDisponible(f"Productos inexistentes: {sorted(faltantes)}.")
    for producto_id, cantidad in items.items():
        productos[producto_id].stock += cantidad
        _guardar(productos[producto_id])
    return list(productos.values())


@transaction.atomic
def ajustar_stock(producto_id, delta):
    delta = int(delta)
    producto = Producto.objects.select_for_update().get(pk=producto_id)
    nuevo = producto.stock + delta
    if nuevo < 0:
        raise StockInsuficiente("El ajuste dejaría el stock en negativo.")
    producto.stock = nuevo
    _guardar(producto)
    return producto


def guardar_imagen(archivo):
    extension = archivo.name.rsplit(".", 1)[-1].lower()
    return default_storage.save(f"productos/{uuid.uuid4().hex}.{extension}", archivo)


def eliminar_imagen(ruta):
    if ruta and default_storage.exists(ruta):
        default_storage.delete(ruta)
