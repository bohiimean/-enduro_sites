import logging

from django.core.management.base import BaseCommand

from worker.scheduler import build_scheduler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Фоновые задачи (APScheduler)"

    def handle(self, *args, **options):
        scheduler = build_scheduler()
        logger.info("worker запущен, задач: %d", len(scheduler.get_jobs()))
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("worker остановлен")
