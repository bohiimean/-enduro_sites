"""Сборка провайдеров и расписание обновлений."""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import config
from .cache import RateCache
from .providers.alfabit import AlfabitWidgetProvider
from .providers.alfabit_client import AlfabitClient
from .providers.base import RateProvider
from .providers.fallback import FallbackProvider
from .providers.investing import InvestingComProvider
from .providers.rapira import RapiraProvider
from .providers.twelvedata import TwelveDataProvider

logger = logging.getLogger(__name__)


def build_cache() -> RateCache:
    cache = RateCache()

    if config.SOURCE_RAPIRA in config.SOURCES_ENABLED:
        cache.register(config.SOURCE_RAPIRA, RapiraProvider())
        logger.info("Источник включён: rapira")

    if config.SOURCE_INVESTING in config.SOURCES_ENABLED:
        provider: RateProvider = InvestingComProvider(chrome_binary=config.CHROME_BINARY_PATH)
        if config.TWELVEDATA_API_KEY:
            provider = FallbackProvider(
                primary=provider,
                secondary=TwelveDataProvider(api_key=config.TWELVEDATA_API_KEY),
            )
            logger.info("Источник включён: investing → TwelveData (запасной)")
        else:
            logger.info("Источник включён: investing (без запасного)")
        cache.register(config.SOURCE_INVESTING, provider)

    if config.SOURCE_ALFABIT in config.SOURCES_ENABLED:
        # Публичные эндпоинты витрины ключей не требуют. Ключи нужны только
        # подписанному запасному пути: без них провайдер работает, но если
        # недокументированный публичный API пропадёт — курс просто не придёт.
        client = None
        if config.ALFABIT_API_KEY and config.ALFABIT_SECRET_KEY:
            client = AlfabitClient(
                api_key=config.ALFABIT_API_KEY,
                secret_key=config.ALFABIT_SECRET_KEY,
                base_url=config.ALFABIT_BASE_URL,
            )
            logger.info("Источник включён: alfabit_showcase (с подписанным запасным путём)")
        else:
            logger.warning(
                "Источник включён: alfabit_showcase (ключей нет — запасного пути не будет)"
            )
        cache.register(
            config.SOURCE_ALFABIT,
            AlfabitWidgetProvider(
                client,
                direction=config.ALFABIT_RATE_DIRECTION,
                base_url=config.ALFABIT_BASE_URL,
                fee_fallback_percent=config.ALFABIT_FEE_PERCENT_FALLBACK,
            ),
        )

    if not cache.keys:
        logger.error("Не включён ни один источник — проверьте SOURCES_ENABLED")
    return cache


def build_scheduler(cache: RateCache) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    for key in cache.keys:
        scheduler.add_job(
            cache.refresh,
            trigger="interval",
            minutes=config.REFRESH_MINUTES,
            args=[key],
            id=f"refresh:{key}",
            replace_existing=True,
            # Скрап investing длиннее интервала быть не должен, но если
            # затянется — второй параллельный запуск не нужен.
            max_instances=1,
            coalesce=True,
        )
    return scheduler


async def warm_up(cache: RateCache) -> None:
    """Первичный прогрев. Запускается фоном, не блокируя старт HTTP-сервера:
    investing берёт 2–3 минуты, и всё это время порт должен уже слушаться —
    иначе healthcheck снаружи посчитает сервис мёртвым."""
    await asyncio.gather(*(cache.refresh(key) for key in cache.keys))
    logger.info("Прогрев завершён")
