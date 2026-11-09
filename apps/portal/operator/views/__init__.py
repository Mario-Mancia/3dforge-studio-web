from .clientes import ClienteAccionView, ClienteOperadorView, ClientesView
from .cotizaciones import (
    CotizacionesView,
    CotizacionOperadorAccionView,
    CotizacionOperadorArchivoView,
    CotizacionOperadorView,
)
from .encargos import (
    EncargoAccionView,
    EncargoArchivoView,
    EncargoDesdeCotizacionView,
    EncargoOperadorView,
    EncargosView,
)
from .facturas import FacturaAccionView, FacturaDesdeEncargoView, FacturaOperadorView, FacturasView
from .notificaciones import NotificacionAccionOperadorView, NotificacionesOperadorView
from .panel import PanelView
from .soporte import SoporteAccionView, SoporteOperadorDetalleView, SoporteOperadorView
