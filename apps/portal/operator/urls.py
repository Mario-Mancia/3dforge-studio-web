from django.urls import path

from . import views

app_name = "operator"

urlpatterns = [
    path("", views.PanelView.as_view(), name="panel"),
    path("cotizaciones/", views.CotizacionesView.as_view(), name="cotizaciones"),
    path("cotizaciones/<int:pk>/", views.CotizacionOperadorView.as_view(), name="cotizacion"),
    path(
        "cotizaciones/<int:pk>/accion/<slug:accion>/",
        views.CotizacionOperadorAccionView.as_view(),
        name="cotizacion_accion",
    ),
    path(
        "cotizaciones/<int:pk>/archivos/<int:archivo_id>/",
        views.CotizacionOperadorArchivoView.as_view(),
        name="cotizacion_archivo",
    ),
    path("cotizaciones/<int:pk>/encargo/", views.EncargoDesdeCotizacionView.as_view(), name="cotizacion_encargo"),
    path("encargos/", views.EncargosView.as_view(), name="encargos"),
    path("encargos/<int:pk>/", views.EncargoOperadorView.as_view(), name="encargo"),
    path("encargos/<int:pk>/accion/<slug:accion>/", views.EncargoAccionView.as_view(), name="encargo_accion"),
    path(
        "encargos/<int:pk>/archivos/<int:archivo_id>/",
        views.EncargoArchivoView.as_view(),
        name="encargo_archivo",
    ),
    path("encargos/<int:pk>/factura/", views.FacturaDesdeEncargoView.as_view(), name="encargo_factura"),
    path("facturas/", views.FacturasView.as_view(), name="facturas"),
    path("facturas/<int:pk>/", views.FacturaOperadorView.as_view(), name="factura"),
    path("facturas/<int:pk>/accion/<slug:accion>/", views.FacturaAccionView.as_view(), name="factura_accion"),
    path("clientes/", views.ClientesView.as_view(), name="clientes"),
]
