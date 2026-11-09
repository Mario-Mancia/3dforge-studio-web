from django.db import models


class ModeloValidado(models.Model):
    campos_texto_opcional = ()

    class Meta:
        abstract = True

    def normalizar(self):
        for campo in self.campos_texto_opcional:
            valor = getattr(self, campo)
            if isinstance(valor, str):
                setattr(self, campo, valor.strip() or None)

    def clean(self):
        super().clean()
        self.normalizar()

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None:
            self.full_clean(validate_constraints=False)
        else:
            nombres = set(update_fields)
            excluir = [
                campo.name
                for campo in self._meta.concrete_fields
                if campo.name not in nombres and campo.attname not in nombres
            ]
            self.clean_fields(exclude=excluir)
        super().save(*args, **kwargs)
