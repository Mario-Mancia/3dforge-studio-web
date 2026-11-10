from django.urls import path

from apps.api.vistas import auth, catalogo, compras, cotizaciones, cuenta, pedidos, seguimiento

app_name = "api"

urlpatterns = [
    path("salud/", cuenta.salud, name="salud"),
    path("negocio/", cuenta.negocio, name="negocio"),
    path("auth/registro/", auth.registro_cuenta, name="registro"),
    path("auth/reenviar-confirmacion/", auth.reenviar_confirmacion, name="reenviar_confirmacion"),
    path("auth/login/", auth.login, name="login"),
    path("auth/refrescar/", auth.refrescar, name="refrescar"),
    path("auth/logout/", auth.cerrar_sesion, name="logout"),
    path("auth/recuperar/", auth.recuperar_password, name="recuperar"),
    path("auth/cambiar-password/", auth.cambiar_password, name="cambiar_password"),
    path("perfil/", cuenta.perfil, name="perfil"),
    path("panel/", cuenta.panel, name="panel"),
    path("catalogo/categorias/", catalogo.categorias, name="categorias"),
    path("catalogo/productos/", catalogo.productos, name="productos"),
    path("catalogo/productos/<int:pk>/", catalogo.producto_detalle, name="producto"),
    path("catalogo/servicios/", catalogo.servicios, name="servicios"),
    path("catalogo/servicios/<int:pk>/", catalogo.servicio_detalle, name="servicio"),
    path("carrito/validar/", compras.validar_carrito, name="carrito_validar"),
    path("compras/", compras.comprar, name="comprar"),
    path("cotizaciones/", cotizaciones.cotizaciones, name="cotizaciones"),
    path("cotizaciones/<int:pk>/", cotizaciones.cotizacion_detalle, name="cotizacion"),
    path("cotizaciones/<int:pk>/archivos/<int:archivo_id>/", cotizaciones.cotizacion_archivo, name="cotizacion_archivo"),
    path("cotizaciones/<int:pk>/<slug:accion>/", cotizaciones.cotizacion_accion, name="cotizacion_accion"),
    path("pedidos/", pedidos.pedidos, name="pedidos"),
    path("pedidos/<int:pk>/", pedidos.pedido_detalle, name="pedido"),
    path("pedidos/<int:pk>/cancelar/", pedidos.pedido_cancelar, name="pedido_cancelar"),
    path("pedidos/<int:pk>/archivos/<int:archivo_id>/", pedidos.pedido_archivo, name="pedido_archivo"),
    path("facturas/", pedidos.facturas, name="facturas"),
    path("facturas/<int:pk>/", pedidos.factura_detalle, name="factura"),
    path("notificaciones/", seguimiento.notificaciones, name="notificaciones"),
    path("notificaciones/contador/", seguimiento.notificaciones_contador, name="notificaciones_contador"),
    path("notificaciones/leer-todas/", seguimiento.notificaciones_leer_todas, name="notificaciones_leer_todas"),
    path("notificaciones/<int:pk>/leer/", seguimiento.notificacion_leer, name="notificacion_leer"),
    path("soporte/", seguimiento.soporte, name="soporte"),
    path("soporte/<int:pk>/", seguimiento.soporte_detalle, name="soporte_detalle"),
    path("soporte/<int:pk>/cerrar/", seguimiento.soporte_cerrar, name="soporte_cerrar"),
]
