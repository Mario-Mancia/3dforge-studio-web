from django.contrib import admin


def registrar(*modelos, **opciones):
    for modelo in modelos:
        atributos = {
            "list_display": [campo.name for campo in modelo._meta.concrete_fields][:6],
            "list_per_page": 50,
            "list_select_related": True,
        }
        atributos.update(opciones)
        admin.site.register(modelo, type(f"{modelo.__name__}Admin", (admin.ModelAdmin,), atributos))
