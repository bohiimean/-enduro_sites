"""Сервис курсов: сырые котировки для сайта и (позже) бота.

Отдаёт ровно то, что сказал источник. Наценки, делитель юаня и тарифные
уровни живут в БД Django и сюда не попадают — иначе цена считалась бы в двух
местах и разъехалась бы при первой же правке в админке.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, status

from . import config
from .auth import require_token
from .cache import RateCache
from .scheduler import build_cache, build_scheduler, warm_up

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

cache: RateCache = RateCache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache
    cache = build_cache()
    scheduler = build_scheduler(cache)
    scheduler.start()
    # Прогрев — фоновой задачей, см. комментарий в warm_up.
    import asyncio

    asyncio.create_task(warm_up(cache))
    logger.info("Сервис курсов запущен, источников: %d", len(cache.keys))
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="enduro rate-service", lifespan=lifespan)


def _entry(key: str) -> dict:
    entry = cache.get(key)
    if entry is None:
        # Источник включён, но ещё не прогрелся или падает. Ключ всё равно
        # присутствует — потребителю важно отличить «не настроен» от «пусто».
        return {"value": None, "fetched_at": None}
    return {
        "value": f"{entry.rate:f}",
        "fetched_at": datetime.fromtimestamp(entry.fetched_at, tz=timezone.utc).isoformat(),
    }


@app.get("/health")
def health() -> dict:
    """Без токена: снаружи этим живёт мониторинг. Значения курсов не отдаёт —
    только возраст, чтобы по открытому эндпоинту нельзя было снимать цену."""
    now = datetime.now(tz=timezone.utc).timestamp()
    sources = {}
    for key in cache.keys:
        entry = cache.get(key)
        sources[key] = {
            "ready": entry is not None,
            "age_seconds": int(now - entry.fetched_at) if entry else None,
        }
    return {"status": "ok", "sources": sources}


@app.get("/rates", dependencies=[Depends(require_token)])
def rates() -> dict:
    return {key: _entry(key) for key in cache.keys}


@app.get("/rates/{key}", dependencies=[Depends(require_token)])
def rate(key: str) -> dict:
    if not cache.is_registered(key):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Источник {key!r} не включён. Доступны: {', '.join(cache.keys) or '—'}",
        )
    return _entry(key)
