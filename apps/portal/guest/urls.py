from django.urls import path

from . import views

app_name = "guest"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("catalogo/", views.CatalogoView.as_view(), name="catalogo"),
    path("servicios/", views.ServiciosView.as_view(), name="servicios"),
    path("acceso/", views.AccesoView.as_view(), name="acceso"),
]
