from django.contrib.auth.models import BaseUserManager

from apps.usuarios.constants import ESTADO_ACTIVO


class UsuarioManager(BaseUserManager):
    def get_by_natural_key(self, correo):
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": correo})

    def _crear(self, correo, password, **extra):
        if not correo:
            raise ValueError("El correo es obligatorio.")
        extra.setdefault("estado_id", ESTADO_ACTIVO)
        usuario = self.model(correo=self.normalize_email(correo).lower(), **extra)
        if password:
            usuario.set_password(password)
        else:
            usuario.set_unusable_password()
        usuario.save(using=self._db)
        return usuario

    def create_user(self, correo, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(correo, password, **extra)

    def create_superuser(self, correo, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra.get("is_staff") is not True or extra.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_staff e is_superuser en True.")
        return self._crear(correo, password, **extra)
