from django.urls import path

from apps.portal.fotos import FotoPerfilClienteView
from . import views

app_name = "customer"

urlpatterns = [
    path("", views.PanelView.as_view(), name="panel"),
    path("tienda/", views.TiendaView.as_view(), name="tienda"),
    path("carrito/", views.CarritoView.as_view(), name="carrito"),
    path("carrito/agregar/<int:pk>/", views.CarritoAgregarView.as_view(), name="carrito_agregar"),
    path("carrito/confirmar/", views.CheckoutView.as_view(), name="checkout"),
    path("cotizar/", views.CotizarView.as_view(), name="cotizar"),
    path("cotizaciones/", views.CotizacionesView.as_view(), name="cotizaciones"),
    path("cotizaciones/<int:pk>/", views.CotizacionDetalleView.as_view(), name="cotizacion"),
    path("cotizaciones/<int:pk>/accion/<slug:accion>/", views.CotizacionAccionView.as_view(), name="cotizacion_accion"),
    path(
        "cotizaciones/<int:pk>/archivos/<int:archivo_id>/",
        views.CotizacionArchivoView.as_view(),
        name="cotizacion_archivo",
    ),
    path("pedidos/", views.PedidosView.as_view(), name="pedidos"),
    path("pedidos/<int:pk>/", views.PedidoDetalleView.as_view(), name="pedido"),
    path("pedidos/<int:pk>/cancelar/", views.PedidoCancelarView.as_view(), name="pedido_cancelar"),
    path("pedidos/<int:pk>/archivos/<int:archivo_id>/", views.PedidoArchivoView.as_view(), name="pedido_archivo"),
    path("facturas/", views.FacturasClienteView.as_view(), name="facturas"),
    path("facturas/<int:pk>/", views.FacturaClienteView.as_view(), name="factura"),
    path("notificaciones/", views.NotificacionesClienteView.as_view(), name="notificaciones"),
    path("notificaciones/accion/<slug:accion>/", views.NotificacionAccionClienteView.as_view(), name="notificacion_accion"),
    path("soporte/", views.SoporteView.as_view(), name="soporte"),
    path("soporte/<int:pk>/", views.SoporteDetalleView.as_view(), name="soporte_detalle"),
    path("soporte/<int:pk>/cerrar/", views.SoporteCerrarView.as_view(), name="soporte_cerrar"),
    path("cuenta/foto/", FotoPerfilClienteView.as_view(), name="cuenta_foto"),
    path("cuenta/", views.CuentaView.as_view(), name="cuenta"),
]
