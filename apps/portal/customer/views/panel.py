from django.views.generic import TemplateView

from apps.portal.mixins import ClienteRequeridoMixin


class PanelView(ClienteRequeridoMixin, TemplateView):
    template_name = "customer/panel.html"
