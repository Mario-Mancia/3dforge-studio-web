from django.urls import path

from apps.portal.cuenta_personal import CuentaPersonalView
from apps.portal.fotos import FotoPerfilPersonalView
from . import views

app_name = "administrator"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("inventario/", views.InventarioView.as_view(), name="inventario"),
    path("inventario/nuevo/", views.ProductoCrearView.as_view(), name="producto_crear"),
    path("inventario/<int:pk>/editar/", views.ProductoEditarView.as_view(), name="producto_editar"),
    path("inventario/<int:pk>/activo/", views.ProductoActivoView.as_view(), name="producto_activo"),
    path("inventario/<int:pk>/stock/", views.ProductoStockView.as_view(), name="producto_stock"),
    path("servicios/", views.ServiciosView.as_view(), name="servicios"),
    path("servicios/nuevo/", views.ServicioCrearView.as_view(), name="servicio_crear"),
    path("servicios/<int:pk>/editar/", views.ServicioEditarView.as_view(), name="servicio_editar"),
    path("servicios/<int:pk>/activo/", views.ServicioActivoView.as_view(), name="servicio_activo"),
    path("servicios/categorias/nueva/", views.CategoriaCrearView.as_view(), name="categoria_crear"),
    path("servicios/categorias/<int:pk>/editar/", views.CategoriaEditarView.as_view(), name="categoria_editar"),
    path("usuarios/", views.UsuariosView.as_view(), name="usuarios"),
    path("usuarios/nuevo/", views.UsuarioCrearView.as_view(), name="usuario_crear"),
    path("usuarios/<int:pk>/editar/", views.UsuarioEditarView.as_view(), name="usuario_editar"),
    path("ventas/", views.VentasView.as_view(), name="ventas"),
    path("ventas/exportar/<slug:tipo>/", views.VentasExportarView.as_view(), name="ventas_exportar"),
    path("cuenta/", CuentaPersonalView.as_view(), name="cuenta"),
    path("cuenta/foto/", FotoPerfilPersonalView.as_view(), name="cuenta_foto"),
    path("configuracion/", views.ConfiguracionView.as_view(), name="configuracion"),
]
