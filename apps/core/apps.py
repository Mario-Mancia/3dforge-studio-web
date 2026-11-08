from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Nucleo"

    def ready(self):
        from apps.core.seeds import sembrar_datos_iniciales

        post_migrate.connect(
            sembrar_datos_iniciales,
            sender=self,
            dispatch_uid="apps.core.sembrar_datos_iniciales",
        )
