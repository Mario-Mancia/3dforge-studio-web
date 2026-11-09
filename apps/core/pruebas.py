import time

from django.db import connections
from django.db.utils import OperationalError
from django.test.runner import DiscoverRunner


class EjecutorPruebas(DiscoverRunner):
    intentos = 5
    espera = 3

    def teardown_databases(self, old_config, **kwargs):
        for intento in range(self.intentos):
            connections.close_all()
            try:
                return super().teardown_databases(old_config, **kwargs)
            except OperationalError as error:
                if intento == self.intentos - 1:
                    print(f"\nAVISO: no se pudo eliminar la base de pruebas ({error}). Elimínela manualmente.")
                    return None
                time.sleep(self.espera)
