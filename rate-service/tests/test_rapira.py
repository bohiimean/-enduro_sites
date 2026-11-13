import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from app.cache import RateCache
from app.providers.rapira import RapiraProvider


class RapiraTests(unittest.IsolatedAsyncioTestCase):
    async def test_rate_limit_preserves_quote_and_waits_before_retry(self):
        provider = RapiraProvider()
        cache = RateCache()
        cache.register("rapira", provider)
        response = MagicMock()
        response.status = 200
        response.json = AsyncMock(return_value={"data": [{"symbol": "USDT/RUB", "close": 90}]})
        session = MagicMock()
        session.get.return_value.__aenter__ = AsyncMock(return_value=response)
        with patch("app.providers.rapira.aiohttp.ClientSession") as client, \
                patch("app.providers.rapira.time.monotonic", return_value=100) as clock:
            client.return_value.__aenter__ = AsyncMock(return_value=session)
            await cache.refresh("rapira")
            first = cache.get("rapira")
            response.status = 429
            response.headers = {"Retry-After": "600"}
            response.raise_for_status.side_effect = aiohttp.ClientResponseError(
                MagicMock(), (), status=429, message="Rate limit")
            await cache.refresh("rapira")
            self.assertIs(cache.get("rapira"), first)
            calls = session.get.call_count
            clock.return_value = 699
            await cache.refresh("rapira")
            self.assertEqual(session.get.call_count, calls)
            clock.return_value = 701
            response.status = 200
            response.raise_for_status.side_effect = None
            await cache.refresh("rapira")
            self.assertEqual(session.get.call_count, calls + 1)
            self.assertIsNot(cache.get("rapira"), first)
