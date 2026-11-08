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
    path("encargos/", views.EncargosView.as_view(), name="encargos"),
    path("clientes/", views.ClientesView.as_view(), name="clientes"),
]
