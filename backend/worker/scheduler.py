"""Расписание фоновых задач.

Три вида задач: обновление котировок, досмотр неоплаченных платежей и досмотр
заявок KYC. Состояние последних двух в БД, поэтому рестарт worker их не теряет
(у бота оба реестра жили в памяти).

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


# Платёж — чаще: человек ждёт подтверждения оплаты, и если он закрыл вкладку,
# менеджер должен увидеть оплату в админке без задержки в минуты.
PAYMENTS_EVERY_SECONDS = 30
# Заявка KYC — реже: быстрый путь (распознавание за секунды) закрывает опрос с
# экрана оплаты, сюда заявка попадает «надолго» — ручная сверка идёт часами.
KYC_EVERY_SECONDS = 60


def _alfabit_job(name: str):
    """Обёртка: ошибка одного круга гасится в лог, расписание живёт дальше."""

    def run() -> None:
        from payments import services
        from payments.alfabit import get_client

        client = get_client()
        if client is None:
            return
        try:
            getattr(services, name)(client)
        except Exception:
            logger.exception("Задача %s упала", name)

    run.__name__ = name
    return run


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

    if settings.ALFABIT_API_KEY and settings.ALFABIT_SECRET_KEY:
        for name, seconds in (
            ("watch_payments", PAYMENTS_EVERY_SECONDS),
            ("watch_kyc", KYC_EVERY_SECONDS),
        ):
            scheduler.add_job(
                _alfabit_job(name), trigger="interval", seconds=seconds, id=name,
                replace_existing=True, max_instances=1, coalesce=True,
            )
        logger.info("Досмотр платежей и KYC включён")
    else:
        logger.warning("Ключи alfabit не заданы — платежи и KYC не досматриваются")

    return scheduler
