from django.urls import path

from . import views

app_name = "customer"

urlpatterns = [
    path("", views.PanelView.as_view(), name="panel"),
    path("tienda/", views.TiendaView.as_view(), name="tienda"),
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
    path("cuenta/", views.CuentaView.as_view(), name="cuenta"),
]
