# API de clientes (app móvil)

Base: `http(s)://<host>:8000/api/` · JSON UTF-8 · fechas ISO-8601 con zona (America/El_Salvador) ·
dinero como **texto** con 2 decimales (`"12.50"`) · rutas con barra final.

**Autenticación:** `POST auth/login/` devuelve `token`; enviar `Authorization: Bearer <token>`.
El token es una sesión de Django de canal `api` (30 días, `API_TOKEN_DIAS`). `auth/refrescar/` lo renueva.

**Errores:** `{"error": {"codigo": "...", "mensaje": "...", "campos": {"campo": ["msg"]}}}`
con estado 400 (datos), 401 (sin sesión/credenciales), 403 (sin permiso/correo sin confirmar),
404, 409 (transición inválida o duplicado), 413/415, 429 (límite/bloqueo) o 500.

**Paginación:** `?pagina=1&por_pagina=20` → `{"resultados":[...],"total":N,"pagina":1,"paginas":P,"hay_mas":bool}`.

| Método y ruta | Sesión | Descripción |
|---|---|---|
| GET `salud/` | no | Comprobar conexión |
| GET `negocio/` | no | Datos del negocio (contacto, logo) |
| POST `auth/registro/` | no | `{nombres, apellidos, correo, telefono?, password, password2?}` → 201; envía correo de confirmación |
| POST `auth/reenviar-confirmacion/` | no | `{correo}` |
| POST `auth/login/` | no | `{correo, password}` → `{token, expira_en, usuario, cliente}` |
| POST `auth/refrescar/` · `auth/logout/` | sí | Renueva/cierra el token |
| POST `auth/recuperar/` | no | `{correo}` → correo con enlace web de restablecimiento |
| POST `auth/cambiar-password/` | sí | `{password_actual, password_nueva}` |
| GET/PUT/PATCH `perfil/` | sí | Ver/editar datos del cliente |
| GET `panel/` | sí | Indicadores y listas cortas |
| GET `catalogo/categorias/` · `catalogo/productos/?q=` · `catalogo/productos/<id>/` · `catalogo/servicios/?categoria=` · `catalogo/servicios/<id>/` | no | Catálogo público |
| POST `carrito/validar/` | sí | `{items:[{producto_id, cantidad}]}` → líneas, totales y problemas |
| POST `compras/` | sí | `{items, token}` (token único por compra, 8–64 caracteres; repetirlo es seguro) → 201 `{duplicado, pedido}` |
| GET/POST `cotizaciones/` | sí | Lista · crear (**multipart**: `servicio, cantidad, descripcion, solicitud, material?, color?, dimensiones?, archivos[]`; o JSON sin archivos) |
| GET `cotizaciones/<id>/` | sí | Detalle con `puede_responder`, `puede_cancelar`, `vencida`, archivos y pedido |
| POST `cotizaciones/<id>/aceptar|rechazar|cancelar/` | sí | Acciones (409 si el estado no lo permite) |
| GET `cotizaciones/<id>/archivos/<aid>/` | sí | Descarga (requiere Bearer) |
| GET `pedidos/` · `pedidos/<id>/` · POST `pedidos/<id>/cancelar/` · GET `pedidos/<id>/archivos/<aid>/` | sí | Pedidos (solo `PENDIENTE` se cancela) |
| GET `facturas/` · `facturas/<id>/` | sí | Facturas con pagos confirmados |
| GET `notificaciones/?no_leidas=1` · `notificaciones/contador/` · POST `notificaciones/<id>/leer/` · `notificaciones/leer-todas/` | sí | Avisos |
| GET/POST `soporte/` · GET `soporte/<id>/` · POST `soporte/<id>/cerrar/` | sí | Soporte (`{asunto, descripcion, prioridad: BAJA\|MEDIA\|ALTA}`) |

Archivos: formatos STL, OBJ, 3MF, STEP/STP, PNG, JPG, PDF; máx. 5 por solicitud y 50 MB c/u (validados por contenido).
