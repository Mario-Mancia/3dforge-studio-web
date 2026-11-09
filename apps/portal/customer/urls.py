from django.urls import path

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
    path("cuenta/", views.CuentaView.as_view(), name="cuenta"),
]
