from django.urls import path

from . import views

app_name = "administrator"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("inventario/", views.InventarioView.as_view(), name="inventario"),
    path("servicios/", views.ServiciosView.as_view(), name="servicios"),
    path("usuarios/", views.UsuariosView.as_view(), name="usuarios"),
    path("ventas/", views.VentasView.as_view(), name="ventas"),
    path("configuracion/", views.ConfiguracionView.as_view(), name="configuracion"),
]
