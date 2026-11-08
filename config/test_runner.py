from django.db import connections
from django.test.runner import DiscoverRunner


class CleanConnectionsRunner(DiscoverRunner):

    def teardown_databases(self, old_config, **kwargs):
        connections.close_all()

        super().teardown_databases(old_config, **kwargs)