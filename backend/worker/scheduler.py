"""Расписание фоновых задач.

Сейчас здесь обновление котировок; опрос статусов платежей и досмотр заявок
KYC приедут на этапе 4.

APScheduler, а не Celery: задач три вида, все периодические, без цепочек и
приоритетов. Redis ради этого не заводим (CLAUDE.md, «Порог пересмотра»).
"""
import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from django.conf import settings

logger = logging.getLogger(__name__)

HEARTBEAT_MINUTES = 15


def _heartbeat() -> None:
    logger.info("worker жив")


def _refresh_quotes() -> None:
    """Единственное место, откуда ходят в сервис курсов.

    Он стоит за границей и отвечает небыстро, а бывает, что и не отвечает.
    Поэтому здесь: ошибка гасится в лог, прежние котировки остаются в БД, и
    витрина покажет их с пометкой времени вместо пустой страницы.
    """
    from pricing.services import RateServiceError, fetch_quotes

    try:
        fetch_quotes()
    except RateServiceError as exc:
        logger.warning("Сервис курсов не ответил: %s", exc)
    except Exception:
        logger.exception("Не удалось обновить котировки")


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_job(_heartbeat, trigger="interval", minutes=HEARTBEAT_MINUTES,
                      id="heartbeat", replace_existing=True)

    if settings.RATE_SERVICE_URL:
        scheduler.add_job(
            _refresh_quotes,
            trigger="interval",
            minutes=settings.RATE_REFRESH_MINUTES,
            id="refresh_quotes",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            # Первый заход сразу после старта: иначе после перезапуска витрина
            # до двадцати минут показывала бы вчерашнюю цену.
            next_run_time=datetime.now(),
        )
        logger.info("Обновление котировок: каждые %d мин", settings.RATE_REFRESH_MINUTES)
    else:
        logger.warning("RATE_SERVICE_URL не задан — котировки обновляться не будут")

    return scheduler
