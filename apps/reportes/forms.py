from datetime import timedelta

from django import forms
from django.utils import timezone

RANGO_MAXIMO_DIAS = 1830


class FiltroFechasForm(forms.Form):
    desde = forms.DateField(required=False)
    hasta = forms.DateField(required=False)


def fechas_filtro(consulta):
    hoy = timezone.localdate()
    desde, hasta, errores = hoy.replace(day=1), hoy, []
    if consulta.get("desde") or consulta.get("hasta"):
        formulario = FiltroFechasForm(consulta)
        if not formulario.is_valid():
            errores.append("Las fechas indicadas no son válidas.")
        else:
            inicio = formulario.cleaned_data.get("desde") or desde
            fin = formulario.cleaned_data.get("hasta") or hoy
            if inicio > fin:
                errores.append("La fecha inicial no puede ser posterior a la final.")
            elif (fin - inicio) > timedelta(days=RANGO_MAXIMO_DIAS):
                errores.append("El rango máximo es de 5 años.")
            else:
                desde, hasta = inicio, fin
    return desde, hasta, errores
