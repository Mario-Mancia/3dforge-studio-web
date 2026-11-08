from django.urls import include, path

urlpatterns = [
    path("cliente/", include("apps.portal.customer.urls")),
    path("operador/", include("apps.portal.operator.urls")),
    path("administrador/", include("apps.portal.administrator.urls")),
    path("", include("apps.portal.guest.urls")),
]
