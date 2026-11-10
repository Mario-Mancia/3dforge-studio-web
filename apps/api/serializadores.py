from decimal import Decimal

from django.core.files.storage import default_storage
from django.utils import timezone

CENTAVO = Decimal("0.01")
PROGRESO_ENCARGO = {
    "PENDIENTE": 25,
    "EN_REVISION": 25,
    "APROBADO": 50,
    "EN_ESPERA": 50,
    "EN_PRODUCCION": 75,
    "FINALIZADO": 100,
    "ENTREGADO": 100,
}


def dinero(valor):
    return None if valor is None else format(Decimal(valor).quantize(CENTAVO), "f")


def cantidad(valor):
    return None if valor is None else format(Decimal(valor).normalize(), "f")


def fecha(valor):
    return timezone.localtime(valor).isoformat() if valor else None


def _absoluta(request, ruta):
    return request.build_absolute_uri(ruta) if request is not None else ruta


def cliente(c):
    return {
        "id": c.pk,
        "tipo_cliente": c.tipo_cliente,
        "nombre_visible": c.nombre_visible,
        "nombres": c.nombres,
        "apellidos": c.apellidos,
        "nombre_empresa": c.nombre_empresa,
        "correo": c.correo,
        "telefono": c.telefono,
        "identificacion_fiscal": c.identificacion_fiscal,
        "direccion": c.direccion,
    }


def usuario(u):
    return {"id": u.pk, "correo": u.correo, "nombres": u.nombres, "apellidos": u.apellidos}


def negocio(c, request=None):
    if c is None:
        return {"nombre": "3DForge Studio", "correo": None, "telefono": None, "direccion": None, "sitio_web": None, "logo_url": None}
    logo = _absoluta(request, default_storage.url(c.logo)) if c.logo else None
    return {
        "nombre": c.nombre_negocio,
        "correo": c.correo,
        "telefono": c.telefono,
        "direccion": c.direccion,
        "sitio_web": c.sitio_web,
        "logo_url": logo,
    }


def producto(p, request=None):
    return {
        "id": p.pk,
        "sku": p.sku,
        "nombre": p.nombre,
        "descripcion": p.descripcion,
        "precio": dinero(p.precio),
        "stock": p.stock,
        "stock_minimo": p.stock_minimo,
        "disponibilidad": p.disponibilidad_codigo,
        "disponibilidad_texto": p.disponibilidad,
        "imagen_url": _absoluta(request, p.imagen_url) if p.imagen else None,
    }


def categoria(c):
    return {"id": c.pk, "nombre": c.nombre, "descripcion": c.descripcion}


def servicio(s):
    return {
        "id": s.pk,
        "categoria_id": s.categoria_id,
        "categoria": s.categoria.nombre,
        "nombre": s.nombre,
        "descripcion": s.descripcion,
        "precio_base": dinero(s.precio_base),
        "requiere_archivo": s.requiere_archivo,
    }


def archivo(a):
    return {
        "id": a.pk,
        "nombre": a.nombre_archivo,
        "formato": a.formato,
        "tamano_bytes": a.tamano_bytes,
        "fecha_subida": fecha(a.fecha_subida),
    }


def linea(d):
    return {
        "id": d.pk,
        "descripcion": d.descripcion,
        "especificaciones": getattr(d, "especificaciones", None) or {},
        "cantidad": cantidad(d.cantidad),
        "precio_unitario": dinero(d.precio_unitario),
        "descuento": dinero(d.descuento),
        "impuesto": dinero(d.impuesto),
        "subtotal": dinero(d.subtotal),
        "servicio_id": getattr(d, "servicio_id", None),
        "producto_id": getattr(d, "producto_id", None),
    }


def _importes(documento):
    return {
        "subtotal": dinero(documento.subtotal),
        "descuento": dinero(documento.descuento),
        "impuesto": dinero(documento.impuesto),
        "total": dinero(documento.total),
    }


def cotizacion_resumen(c):
    vencida = c.estado == "ENVIADA" and c.fecha_vencimiento is not None and c.fecha_vencimiento < timezone.now()
    return {
        "id": c.pk,
        "codigo": c.codigo,
        "estado": c.estado,
        "estado_texto": c.get_estado_display(),
        "fecha_emision": fecha(c.fecha_emision),
        "fecha_vencimiento": fecha(c.fecha_vencimiento),
        "plazo_entrega_dias": c.plazo_entrega_dias,
        **_importes(c),
        "vencida": vencida,
        "puede_responder": c.estado == "ENVIADA" and not vencida,
        "puede_cancelar": c.estado == "SOLICITADA",
    }


def cotizacion_detalle(c, encargo=None):
    datos = cotizacion_resumen(c)
    datos.update(
        {
            "solicitud": c.solicitud,
            "observaciones": c.observaciones,
            "lineas": [linea(d) for d in c.detalles.all()],
            "archivos": [archivo(a) for a in c.archivos.all()],
            "pedido": {"id": encargo.pk, "codigo": encargo.codigo} if encargo is not None else None,
        }
    )
    return datos


def encargo_resumen(e):
    return {
        "id": e.pk,
        "codigo": e.codigo,
        "estado": e.estado,
        "estado_texto": e.get_estado_display(),
        "progreso": PROGRESO_ENCARGO.get(e.estado),
        "fecha_solicitud": fecha(e.fecha_solicitud),
        "fecha_entrega_estimada": fecha(e.fecha_entrega_estimada),
        "fecha_entrega_real": fecha(e.fecha_entrega_real),
        "descripcion": e.descripcion,
        "cotizacion_id": e.cotizacion_id,
        **_importes(e),
        "puede_cancelar": e.estado == "PENDIENTE",
    }


def encargo_detalle(e):
    datos = encargo_resumen(e)
    responsable = e.empleado_responsable.usuario.nombre_completo if e.empleado_responsable_id else None
    datos.update(
        {
            "responsable": responsable,
            "lineas": [{**linea(d), "archivos": [archivo(a) for a in d.archivos.all()]} for d in e.detalles.all()],
            "historial": [
                {
                    "estado_anterior": h.estado_anterior,
                    "estado_nuevo": h.estado_nuevo,
                    "estado_nuevo_texto": h.get_estado_nuevo_display(),
                    "comentario": h.comentario,
                    "fecha": fecha(h.fecha_cambio),
                }
                for h in e.historial.all()
            ],
        }
    )
    return datos


def factura_resumen(f):
    return {
        "id": f.pk,
        "numero": f.numero_factura,
        "estado": f.estado,
        "estado_texto": f.get_estado_display(),
        "fecha_emision": fecha(f.fecha_emision),
        "fecha_vencimiento": fecha(f.fecha_vencimiento),
        "total": dinero(f.total),
        "saldo_pendiente": dinero(f.saldo_pendiente),
        "pedido_id": f.encargo_id,
    }


def factura_detalle(f):
    datos = factura_resumen(f)
    datos.update(
        {
            "nombre_facturacion": f.nombre_facturacion,
            "identificacion_fiscal": f.identificacion_fiscal,
            "direccion_facturacion": f.direccion_facturacion,
            **_importes(f),
            "lineas": [linea(d) for d in f.detalles.all()],
            "pagos": [
                {
                    "id": p.pk,
                    "monto": dinero(p.monto),
                    "fecha_pago": fecha(p.fecha_pago),
                    "referencia": p.referencia,
                    "metodo": p.metodo_pago.nombre,
                }
                for p in f.pagos.all()
                if p.estado == "CONFIRMADO"
            ],
            "aviso": "Los pagos en efectivo se coordinan con el equipo.",
        }
    )
    return datos


def notificacion(n):
    return {
        "id": n.pk,
        "titulo": n.titulo,
        "mensaje": n.mensaje,
        "tipo": n.tipo,
        "referencia_id": n.referencia_id,
        "leida": n.leida,
        "fecha": fecha(n.fecha_creacion),
    }


def soporte(s):
    return {
        "id": s.pk,
        "asunto": s.asunto,
        "descripcion": s.descripcion,
        "prioridad": s.prioridad,
        "prioridad_texto": s.get_prioridad_display(),
        "estado": s.estado,
        "estado_texto": s.get_estado_display(),
        "creada_en": fecha(s.creado_en),
        "actualizada_en": fecha(s.actualizado_en),
    }
