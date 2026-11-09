from django.urls import include, path

from apps.portal.validacion import ValidarCampoView
from apps.portal.views import RedireccionPorRolView

urlpatterns = [
    path("ir/", RedireccionPorRolView.as_view(), name="redirigir"),
    path("validar/<slug:clave>/", ValidarCampoView.as_view(), name="validar_campo"),
    path("cliente/", include("apps.portal.customer.urls")),
    path("operador/", include("apps.portal.operator.urls")),
    path("administrador/", include("apps.portal.administrator.urls")),
    path("", include("apps.portal.guest.urls")),
]
