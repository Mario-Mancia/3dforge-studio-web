from apps.api import serializadores as ser
from apps.api.autenticacion import api
from apps.api.respuestas import ErrorAPI, exito, leer_json
from apps.core.calculos import totales_documento
from apps.encargos.selectors import encargos as selectores
from apps.encargos.services import compras


@api(("POST",))
def validar_carrito(request):
    datos = leer_json(request)
    try:
        lineas = compras.lineas_de_items(datos.get("items"))
    except compras.ErrorCompra as error:
        raise ErrorAPI(str(error), "carrito_invalido", 400)
    calculos = [linea["calculo"] for linea in lineas if linea["calculo"]]
    totales = totales_documento(calculos)
    return exito(
        {
            "lineas": [
                {
                    "producto_id": linea["producto_id"],
                    "producto": ser.producto(linea["producto"], request) if linea["producto"] else None,
                    "cantidad": linea["cantidad"],
                    "disponible": linea["disponible"],
                    "subtotal": ser.dinero(linea["calculo"]["subtotal"]) if linea["calculo"] else None,
                    "impuesto": ser.dinero(linea["calculo"]["impuesto"]) if linea["calculo"] else None,
                }
                for linea in lineas
            ],
            "totales": {clave: ser.dinero(valor) for clave, valor in totales.items()},
            "hay_problemas": any(not linea["disponible"] for linea in lineas),
        }
    )


@api(("POST",))
def comprar(request):
    datos = leer_json(request)
    try:
        encargo = compras.confirmar_compra_api(request.cliente, request.usuario, datos.get("items"), datos.get("token"))
    except compras.CompraDuplicada as duplicada:
        previo = selectores.obtener_del_cliente(request.cliente, duplicada.encargo_id) if duplicada.encargo_id else None
        if previo is None:
            raise ErrorAPI("La compra ya está en proceso o fue procesada. Revise sus pedidos.", "compra_duplicada", 409)
        return exito({"duplicado": True, "pedido": ser.encargo_detalle(previo)})
    except compras.ErrorCompra as error:
        raise ErrorAPI(str(error), "compra_invalida", 400)
    pedido = selectores.obtener_del_cliente(request.cliente, encargo.pk)
    return exito({"duplicado": False, "pedido": ser.encargo_detalle(pedido)}, 201)
