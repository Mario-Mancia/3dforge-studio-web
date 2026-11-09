from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.views import View

from apps.catalogo.forms.catalogo import CategoriaForm, ProductoForm, ServicioForm
from apps.catalogo.models import CategoriaServicio, Producto, Servicio
from apps.clientes.forms.clientes import PerfilClienteForm
from apps.clientes.services.clientes import asegurar_cliente
from apps.cotizaciones.forms.cotizaciones import SolicitudCotizacionForm
from apps.pagos.forms.pagos import AnulacionForm, PagoForm
from apps.usuarios.constants import GRUPO_ADMINISTRADOR, GRUPO_CLIENTE, GRUPO_OPERADOR
from apps.usuarios.forms.usuarios import EmpleadoCrearForm, UsuarioEditarForm
from apps.usuarios.models import Usuario


def _instancia(modelo, pk):
    return modelo.objects.filter(pk=pk).first() if pk else None


def _usuario(request, datos, pk):
    usuario = _instancia(Usuario, pk)
    return UsuarioEditarForm(datos, usuario=usuario) if usuario else None


FORMULARIOS = {
    "perfil": ((GRUPO_CLIENTE,), lambda r, d, pk: PerfilClienteForm(d, instance=asegurar_cliente(r.user))),
    "cotizar": ((GRUPO_CLIENTE,), lambda r, d, pk: SolicitudCotizacionForm(d)),
    "producto": ((GRUPO_ADMINISTRADOR,), lambda r, d, pk: ProductoForm(d, instance=_instancia(Producto, pk))),
    "servicio": ((GRUPO_ADMINISTRADOR,), lambda r, d, pk: ServicioForm(d, instance=_instancia(Servicio, pk))),
    "categoria": ((GRUPO_ADMINISTRADOR,), lambda r, d, pk: CategoriaForm(d, instance=_instancia(CategoriaServicio, pk))),
    "empleado": ((GRUPO_ADMINISTRADOR,), lambda r, d, pk: EmpleadoCrearForm(d)),
    "usuario": ((GRUPO_ADMINISTRADOR,), _usuario),
    "pago": ((GRUPO_OPERADOR, GRUPO_ADMINISTRADOR), lambda r, d, pk: PagoForm(d)),
    "anulacion": ((GRUPO_OPERADOR, GRUPO_ADMINISTRADOR), lambda r, d, pk: AnulacionForm(d)),
}


class ValidarCampoView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, clave):
        entrada = FORMULARIOS.get(clave)
        if entrada is None:
            raise Http404
        roles, fabrica = entrada
        if not request.user.tiene_algun_rol(roles):
            raise PermissionDenied
        campo = request.POST.get("campo", "")
        pk = request.POST.get("pk", "")
        formulario = fabrica(request, request.POST, int(pk) if pk.isdigit() else None)
        if formulario is None or campo not in formulario.fields:
            return JsonResponse({"valido": True, "errores": []})
        formulario.full_clean()
        errores = [str(error) for error in formulario.errors.get(campo, [])]
        return JsonResponse({"valido": not errores, "errores": errores})
