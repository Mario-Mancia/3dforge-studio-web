from django.db.models import F, Q

from apps.catalogo.models import CategoriaServicio, Producto, Servicio


def productos_publicos(busqueda=""):
    consulta = Producto.objects.filter(activo=True).order_by("nombre")
    if busqueda:
        consulta = consulta.filter(
            Q(nombre__icontains=busqueda) | Q(sku__icontains=busqueda) | Q(descripcion__icontains=busqueda)
        )
    return consulta


def productos_destacados(limite=4):
    return productos_publicos().filter(stock__gt=0)[:limite]


def servicios_publicos(categoria_id=None):
    consulta = Servicio.objects.filter(activo=True, categoria__activo=True).select_related("categoria")
    if categoria_id:
        consulta = consulta.filter(categoria_id=categoria_id)
    return consulta.order_by("categoria__nombre", "nombre")


def categorias_publicas():
    return CategoriaServicio.objects.filter(activo=True).order_by("nombre")


def productos_admin(busqueda="", solo_bajo_stock=False):
    consulta = Producto.objects.order_by("nombre")
    if busqueda:
        consulta = consulta.filter(Q(nombre__icontains=busqueda) | Q(sku__icontains=busqueda))
    if solo_bajo_stock:
        consulta = consulta.filter(stock__lte=F("stock_minimo"))
    return consulta
