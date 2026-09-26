"""Урезанный клиент Alfabit integration API — только курс конвертера.

Полная версия живёт в боте (`bot/services/alfabit/client.py`) и переезжает в
Django на этапе 4: там нужны checkout, KYC и загрузка документов. Сервису
курсов из всего API нужен один подписанный запрос, и тащить сюда триста строк
с платёжными методами незачем — лишние возможности на машине за границей.

Подпись (проверено на боевых ключах 06.08.2026):
    X-API-Key:       публичный ключ pk_live_...
    X-API-Signature: HMAC_SHA256(secret_key, message)
    X-API-Timestamp: unix-время в секундах (живёт 5 минут)
где message = "{timestamp}{METHOD}{path}{body}".

Наружу клиент бросает только AlfabitError, включая обрывы связи и не-JSON
ответы: alfabit стоит за Cloudflare и уже отдавал 522 с HTML-страницей вместо
JSON, а транспортное исключение пролетало бы мимо `except AlfabitError`.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from decimal import Decimal
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_API_PREFIX = "/api"
_TIMEOUT = aiohttp.ClientTimeout(total=20)


class AlfabitError(RuntimeError):
    def __init__(self, code: str, message: str, status: int | None = None):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(f"{code}: {message}")


class AlfabitClient:
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://alfabit.org"):
        self._api_key = api_key
        self._secret_key = secret_key.encode()
        self._base_url = base_url.rstrip("/")

    def _sign(self, method: str, signed_path: str, body: str) -> dict[str, str]:
        timestamp = str(int(time.time()))
        message = f"{timestamp}{method.upper()}{signed_path}{body}"
        signature = hmac.new(self._secret_key, message.encode(), hashlib.sha256).hexdigest()
        return {
            "X-API-Key": self._api_key,
            "X-API-Signature": signature,
            "X-API-Timestamp": timestamp,
        }

    @staticmethod
    def _signed_path(path: str, params: dict[str, Any] | None) -> str:
        """Query включаем в подпись. Сервер проверяет подпись и без него, но
        полагаться на это незачем."""
        if not params:
            return path
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{path}?{query}"

    @staticmethod
    def _unwrap(payload: Any, status: int) -> Any:
        # Часть ошибок (403 PERMISSION_DENIED и т.п.) приходит завёрнутой в
        # FastAPI-конверт {"detail": {success/error/ts}} — разворачиваем, иначе
        # код и текст ошибки терялись бы внутри строки HTTP_ERROR.
        if isinstance(payload, dict) and isinstance(payload.get("detail"), dict):
            payload = payload["detail"]
        if isinstance(payload, dict) and payload.get("success") is False:
            err = payload.get("error") or {}
            raise AlfabitError(err.get("code", "UNKNOWN"), err.get("message", ""), status)
        if status >= 400:
            detail = payload.get("detail") if isinstance(payload, dict) else None
            raise AlfabitError("HTTP_ERROR", str(detail) if detail else f"status {status}", status)
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    async def converter_fiat_rate(
        self, crypto: str = "USDT", fiat: str = "RUB", direction: str = "buy"
    ) -> Decimal:
        """GET /api/v1/integration/converter/fiat/rate — курс крипто/фиат со спредом."""
        path = _API_PREFIX + "/v1/integration/converter/fiat/rate"
        params = {"crypto": crypto, "fiat": fiat, "direction": direction}
        headers = self._sign("GET", self._signed_path(path, params), "")
        headers["Content-Type"] = "application/json"

        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.get(
                    self._base_url + path, params=params, headers=headers
                ) as resp:
                    try:
                        payload = await resp.json(content_type=None)
                    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                        snippet = " ".join((await resp.text())[:200].split())
                        raise AlfabitError(
                            "BAD_RESPONSE",
                            f"ответ не в формате JSON (HTTP {resp.status}): {snippet}",
                            resp.status,
                        ) from None
                    data = self._unwrap(payload, resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            raise AlfabitError("NETWORK", f"{type(exc).__name__}: {exc}") from exc

        return Decimal(str(data["rate"]))
