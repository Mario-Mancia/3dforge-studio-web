from django.views.generic import TemplateView


class CatalogoView(TemplateView):
    template_name = "guest/catalogo.html"
