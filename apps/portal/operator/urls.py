from django.urls import path

from apps.portal.cuenta_personal import CuentaPersonalView
from apps.portal.fotos import FotoPerfilPersonalView
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
    path("clientes/<int:pk>/", views.ClienteOperadorView.as_view(), name="cliente"),
    path("clientes/<int:pk>/accion/<slug:accion>/", views.ClienteAccionView.as_view(), name="cliente_accion"),
    path("soporte/", views.SoporteOperadorView.as_view(), name="soporte"),
    path("soporte/<int:pk>/", views.SoporteOperadorDetalleView.as_view(), name="soporte_detalle"),
    path("soporte/<int:pk>/accion/<slug:accion>/", views.SoporteAccionView.as_view(), name="soporte_accion"),
    path("cuenta/", CuentaPersonalView.as_view(), name="cuenta"),
    path("cuenta/foto/", FotoPerfilPersonalView.as_view(), name="cuenta_foto"),
    path("notificaciones/", views.NotificacionesOperadorView.as_view(), name="notificaciones"),
    path("notificaciones/accion/<slug:accion>/", views.NotificacionAccionOperadorView.as_view(), name="notificacion_accion"),
]
