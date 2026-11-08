from django.urls import path

from . import views

app_name = "guest"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("catalogo/", views.CatalogoView.as_view(), name="catalogo"),
    path("catalogo/<int:pk>/", views.ProductoDetalleView.as_view(), name="producto"),
    path("servicios/", views.ServiciosView.as_view(), name="servicios"),
    path("servicios/<int:pk>/", views.ServicioDetalleView.as_view(), name="servicio"),
    path("acceso/", views.AccesoView.as_view(), name="acceso"),
]
