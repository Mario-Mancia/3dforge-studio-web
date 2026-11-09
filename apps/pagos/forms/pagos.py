from decimal import Decimal

from django import forms

from apps.pagos.models import MetodoPago
from apps.pagos.selectors.pagos import metodos_activos


class PagoForm(forms.Form):
    metodo = forms.ModelChoiceField(queryset=MetodoPago.objects.none(), label="Método de pago")
    monto = forms.DecimalField(min_value=Decimal("0.01"), max_digits=12, decimal_places=2, label="Monto")
    referencia = forms.CharField(required=False, max_length=120, label="Referencia")
    observaciones = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metodo"].queryset = metodos_activos()


class AnulacionForm(forms.Form):
    motivo = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 2}), label="Motivo")
