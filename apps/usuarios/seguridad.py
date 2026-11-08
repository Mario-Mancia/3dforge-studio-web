def obtener_identificador(request, credentials=None):
    credentials = credentials or {}
    for clave in ("correo", "email", "login", "username"):
        valor = credentials.get(clave)
        if not valor and request is not None and hasattr(request, "POST"):
            valor = request.POST.get(clave)
        if valor:
            return str(valor).strip().lower()
    return None
