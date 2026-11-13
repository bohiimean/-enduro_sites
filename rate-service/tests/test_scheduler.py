import unittest
from unittest.mock import patch

from app import config
from app.scheduler import build_cache, build_scheduler


class DisabledAlfabitTests(unittest.TestCase):
    def test_old_source_list_does_not_start_alfabit(self):
        with patch.object(config, "SOURCES_ENABLED", list(config.ALL_SOURCES)), \
                patch("app.scheduler.InvestingComProvider") as investing, \
                patch("app.scheduler.AlfabitClient") as client, \
                patch("app.scheduler.AlfabitWidgetProvider") as provider:
            cache = build_cache()
        self.assertEqual(set(cache.keys), {"rapira"})
        investing.assert_not_called()
        client.assert_not_called()
        provider.assert_not_called()

    def test_rapira_refreshes_every_90_seconds(self):
        with patch.object(config, "SOURCES_ENABLED", ["rapira"]):
            job = build_scheduler(build_cache()).get_job("refresh:rapira")
        self.assertEqual(job.trigger.interval.total_seconds(), 90)
