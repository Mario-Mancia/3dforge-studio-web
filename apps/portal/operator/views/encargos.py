from django.views.generic import TemplateView

from apps.portal.mixins import OperadorRequeridoMixin


class EncargosView(OperadorRequeridoMixin, TemplateView):
    template_name = "operator/encargos.html"
