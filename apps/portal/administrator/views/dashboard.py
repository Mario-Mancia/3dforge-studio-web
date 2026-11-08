from django.views.generic import TemplateView

from apps.portal.mixins import AdministradorRequeridoMixin


class DashboardView(AdministradorRequeridoMixin, TemplateView):
    template_name = "administrator/dashboard.html"
