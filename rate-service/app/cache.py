"""Кеш котировок в памяти. Перенос `bot/services/rate_cache.py`.

Хранилище намеренно не переживает рестарт: историю держит Django в
PostgreSQL, а сервису достаточно последнего значения. После перезапуска
источники прогреваются заново — быстрые за секунды, investing за 2–3 минуты,
и всё это время он просто отдаётся пустым.
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from decimal import Decimal

from .providers.base import RateProvider

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    rate: Decimal
    fetched_at: float


class RateCache:
    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._providers: dict[str, RateProvider] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def register(self, key: str, provider: RateProvider) -> None:
        self._providers[key] = provider
        self._locks[key] = asyncio.Lock()

    def is_registered(self, key: str) -> bool:
        return key in self._providers

    @property
    def keys(self) -> list[str]:
        return list(self._providers)

    async def refresh(self, key: str, max_age_seconds: float | None = None) -> None:
        lock = self._locks[key]
        async with lock:
            if max_age_seconds is not None:
                cached = self._store.get(key)
                if cached and time.time() - cached.fetched_at < max_age_seconds:
                    return
            provider = self._providers[key]
            try:
                rate = await provider.get_rate()
            except Exception:
                # Прежнее значение не затираем: устаревшая цена лучше, чем её
                # отсутствие, а возраст видно по fetched_at.
                logger.exception("Не удалось обновить котировку key=%s", key)
                return
            self._store[key] = CacheEntry(rate=rate, fetched_at=time.time())
            logger.info("Котировка обновлена: %s=%s", key, rate)

    def get(self, key: str) -> CacheEntry | None:
        return self._store.get(key)
