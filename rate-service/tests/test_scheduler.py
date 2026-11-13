import unittest
from unittest.mock import patch

from app import config
from app.scheduler import build_cache


class DisabledAlfabitTests(unittest.TestCase):
    def test_old_source_list_does_not_start_alfabit(self):
        with patch.object(config, "SOURCES_ENABLED", list(config.ALL_SOURCES)), \
                patch("app.scheduler.AlfabitClient") as client, \
                patch("app.scheduler.AlfabitWidgetProvider") as provider:
            cache = build_cache()
        self.assertEqual(set(cache.keys), {"rapira", "investing"})
        client.assert_not_called()
        provider.assert_not_called()
