from django.views.generic import TemplateView

from apps.portal.mixins import OperadorRequeridoMixin


class PanelView(OperadorRequeridoMixin, TemplateView):
    template_name = "operator/panel.html"
