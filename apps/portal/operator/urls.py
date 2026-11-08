from django.urls import path

from . import views

app_name = "operator"

urlpatterns = [
    path("", views.PanelView.as_view(), name="panel"),
    path("cotizaciones/", views.CotizacionesView.as_view(), name="cotizaciones"),
    path("encargos/", views.EncargosView.as_view(), name="encargos"),
    path("clientes/", views.ClientesView.as_view(), name="clientes"),
]
