from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import ListView

from apps.clientes.models import Cliente
from apps.core.utiles import mensaje_de
from apps.crm.forms.crm import InteraccionForm, NotaForm
from apps.crm.selectors import crm as selectors
from apps.crm.services import crm as servicios
from apps.portal.mixins import OperadorRequeridoMixin


class ClientesView(OperadorRequeridoMixin, ListView):
    template_name = "operator/clientes.html"
    context_object_name = "clientes"
    paginate_by = 20

    def get_queryset(self):
        return selectors.clientes_para_operador(self.request.GET.get("q", "").strip())

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "").strip()
        return contexto


class ClienteOperadorView(OperadorRequeridoMixin, View):
    template_name = "operator/cliente.html"

    def get(self, request, pk):
        datos = selectors.datos_cliente(pk)
        if datos is None:
            raise Http404
        datos.update({"form_nota": NotaForm(), "form_interaccion": InteraccionForm()})
        return render(request, self.template_name, datos)


class ClienteAccionView(OperadorRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, accion):
        if accion not in ("nota", "interaccion"):
            raise Http404
        try:
            if accion == "nota":
                form = NotaForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("La nota no es válida.")
                servicios.agregar_nota(pk, request.user, form.cleaned_data["contenido"])
                messages.success(request, "Nota agregada.")
            else:
                form = InteraccionForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("La interacción no es válida.")
                datos = form.cleaned_data
                servicios.registrar_interaccion(pk, request.user, datos["tipo"], datos["asunto"], datos["descripcion"])
                messages.success(request, "Interacción registrada.")
        except Cliente.DoesNotExist:
            raise Http404
        except (servicios.ErrorCRM, ValidationError) as error:
            messages.error(request, mensaje_de(error))
        return redirect("operator:cliente", pk=pk)
