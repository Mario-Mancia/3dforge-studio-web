from django.urls import path

from . import views

app_name = "customer"

urlpatterns = [
    path("", views.PanelView.as_view(), name="panel"),
    path("tienda/", views.TiendaView.as_view(), name="tienda"),
    path("cotizar/", views.CotizarView.as_view(), name="cotizar"),
    path("pedidos/", views.PedidosView.as_view(), name="pedidos"),
    path("cuenta/", views.CuentaView.as_view(), name="cuenta"),
]
