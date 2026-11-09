from .configuracion import ConfiguracionView
from .dashboard import DashboardView
from .inventario import (
    InventarioView,
    ProductoActivoView,
    ProductoCrearView,
    ProductoEditarView,
    ProductoStockView,
)
from .servicios import (
    CategoriaCrearView,
    CategoriaEditarView,
    ServicioActivoView,
    ServicioCrearView,
    ServicioEditarView,
    ServiciosView,
)
from .usuarios import UsuarioCrearView, UsuarioEditarView, UsuariosView
from .ventas import VentasExportarView, VentasView
