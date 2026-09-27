"""Клиент Alfabit integration API (подпись HMAC-SHA256).

Перенос `bot/services/alfabit/client.py` почти дословно. Отличие одно: бот
асинхронный (aiohttp), Django — нет, поэтому сеть здесь на `requests`. Логика
подписи, разворачивания ошибок и нормализации телефона не менялась.

Документация: https://alfabit.org/ru/api-docs (SPA — разделы Converter / Checkout).

Каждый запрос подписывается тремя заголовками:
    X-API-Key:       публичный ключ pk_live_...
    X-API-Signature: HMAC_SHA256(secret_key, message)
    X-API-Timestamp: unix-время в секундах (живёт 5 минут)
где message = "{timestamp}{METHOD}{path}{body}".

Проверено на боевых ключах (06.08.2026):
- GET с query подписывается одинаково успешно и с query, и без него — сервер
  проверяет подпись без учёта query-строки. Оставили вариант с query.
- multipart подписывается с пустым body: запрос без файла доходит до валидации
  (422 "field required"), а не отбивается по INVALID_SIGNATURE.

payer_ip у сайта настоящий — то, чего у бота не было в принципе (Telegram не
отдаёт IP пользователя, и туда слался IP сервера по согласованию с поддержкой).

Наружу клиент бросает только AlfabitError — включая обрывы связи, таймауты и
не-JSON ответы. Иначе транспортное исключение пролетало бы мимо `except
AlfabitError` во view и превращалось в 500 посреди загрузки паспорта. Alfabit
стоит за Cloudflare и уже отдавал 522 с HTML-страницей вместо JSON.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from decimal import Decimal
from typing import IO, Any

import requests
from django.conf import settings

_API_PREFIX = "/api"
# Короче, чем у бота (20 с): здесь клиент зовётся из HTTP-запроса человека, и
# gunicorn-воркер всё это время занят.
_TIMEOUT = 15


class AlfabitError(RuntimeError):
    """Ошибка обращения к Alfabit API.

    code — либо код из ответа сервиса, либо один из транспортных:
    NETWORK (обрыв/таймаут), BAD_RESPONSE (ответ не JSON), HTTP_ERROR.
    """

    def __init__(self, code: str, message: str, status: int | None = None):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(f"{code}: {message}")


# Ошибки, где виноват не запрос, а связь или сам сервис: пользователю про них
# нужно сказать одно и то же — «попробуйте позже».
TRANSPORT_ERROR_CODES = frozenset({"NETWORK", "BAD_RESPONSE"})

# Ошибки доступа: у ключа нет прав / подпись не принята. Пользователь тут
# бессилен — повторять попытку бессмысленно, чинится в кабинете alfabit.
ACCESS_ERROR_CODES = frozenset({"PERMISSION_DENIED", "UNAUTHORIZED", "FORBIDDEN", "INVALID_SIGNATURE"})


def is_access_error(exc: AlfabitError) -> bool:
    return exc.code in ACCESS_ERROR_CODES or exc.status in (401, 403)


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
    def _path_phone(phone: str) -> str:
        """Телефон для URL — только цифры.

        Дока требует явно: «в path телефона "+" не ставьте (иначе + декодируется
        как пробел): /payers/79001234567, не /payers/+79001234567». Проверено
        16.08.2026 — сейчас сервер принимает обе формы и отдаёт одну и ту же
        запись, но полагаться на это незачем. В JSON-теле «+» оставляем, там он
        разрешён и нормализуется на их стороне.
        """
        return "".join(ch for ch in phone if ch.isdigit())

    @staticmethod
    def _signed_path(path: str, params: dict[str, Any] | None) -> str:
        """Путь для подписи. Query включаем в подпись."""
        if not params:
            return path
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{path}?{query}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        path = _API_PREFIX + path if not path.startswith(_API_PREFIX) else path
        body = json.dumps(json_body, separators=(",", ":")) if json_body is not None else ""
        headers = self._sign(method, self._signed_path(path, params), body)
        headers["Content-Type"] = "application/json"
        return self._perform(
            method, self._base_url + path, headers=headers, params=params, data=body or None
        )

    def _perform(self, method: str, url: str, *, headers: dict[str, str], **kwargs: Any) -> Any:
        """Единственное место, где живёт сеть: всё, что может прилететь от
        requests, превращается в AlfabitError."""
        try:
            resp = requests.request(method, url, headers=headers, timeout=_TIMEOUT, **kwargs)
        except requests.RequestException as exc:
            raise AlfabitError("NETWORK", f"{type(exc).__name__}: {exc}") from exc
        try:
            payload = resp.json()
        except ValueError:
            # Cloudflare и прочие прокси отдают HTML — в лог кусок тела, иначе
            # причину 5xx потом не восстановить.
            snippet = " ".join(resp.text[:200].split())
            raise AlfabitError(
                "BAD_RESPONSE",
                f"ответ не в формате JSON (HTTP {resp.status_code}): {snippet}",
                resp.status_code,
            ) from None
        return self._unwrap(payload, resp.status_code)

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
            # FastAPI-ошибки приходят без конверта success/error: {"detail": ...}
            detail = payload.get("detail") if isinstance(payload, dict) else None
            raise AlfabitError("HTTP_ERROR", str(detail) if detail else f"status {status}", status)
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    # ---- Курс (Converter, «обменник») -------------------------------------

    def converter_fiat_rate(
        self, crypto: str = "USDT", fiat: str = "RUB", direction: str = "buy"
    ) -> Decimal:
        """GET /api/v1/integration/converter/fiat/rate — курс крипто/фиат с их спредом."""
        data = self._request(
            "GET",
            "/v1/integration/converter/fiat/rate",
            params={"crypto": crypto, "fiat": fiat, "direction": direction},
        )
        return Decimal(str(data["rate"]))

    # ---- Checkout (RUB / СБП + KYC) ----------------------------------------

    def create_checkout_payment(
        self,
        *,
        amount: str,
        payer_phone: str,
        payer_ip: str,
        external_payment_id: str,
        description: str | None = None,
        payer_user_agent: str | None = None,
        payer_device_id: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """POST /api/v1/integration/checkout/payments — создать RUB-платёж.

        Возможные ответы (в data):
          status=kyc_required  → нужна верификация, поле upload_documents_endpoint
          status=created       → payment_uid готов, дальше get_checkout_payment(uid)
        """
        body: dict[str, Any] = {
            "amount": amount,
            "payer_phone": payer_phone,
            "payer_ip": payer_ip,
            "external_payment_id": external_payment_id,
        }
        if description:
            body["description"] = description
        if payer_user_agent:
            body["payer_user_agent"] = payer_user_agent
        if payer_device_id:
            body["payer_device_id"] = payer_device_id
        if channel:
            body["channel"] = channel
        return self._request("POST", "/v1/integration/checkout/payments", json_body=body)

    def get_checkout_payment(self, uid: str) -> dict[str, Any]:
        """GET /api/v1/integration/checkout/payments/{uid} — статус + qr_url/qr_payload."""
        return self._request("GET", f"/v1/integration/checkout/payments/{uid}")

    def get_payer(self, phone: str) -> dict[str, Any]:
        """GET /api/v1/integration/checkout/payers/{phone} — статус KYC плательщика.

        Отдаёт kyc_status (not_started|pending|approved|rejected), processing,
        manual_review и expected_payer_name. Поля processing и manual_review
        различают три разных «pending»: идёт распознавание, заявку забрал
        оператор, ждём документ.
        """
        return self._request("GET", f"/v1/integration/checkout/payers/{self._path_phone(phone)}")

    def upload_payer_document(
        self,
        phone: str,
        doc_type: str,
        file: IO[bytes],
        filename: str,
        *,
        payer_ip: str | None = None,
        content_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """POST /api/v1/integration/checkout/payers/{phone}/documents (multipart).

        doc_type: passport_main | passport_registration | selfie.
        По умолчанию профиль приёма требует passport_main + passport_registration.
        Ответ отдаётся сразу с processing=true — финальный статус забирать
        опросом get_payer(phone). Повторная загрузка того же doc_type безопасна.
        Подпись — с пустым body (проверено, см. модульный docstring).

        `file` — объект в памяти (см. payments/uploads.py): байты паспорта не
        ложатся ни в MEDIA, ни во временные файлы.

        В ответе приходит low_confidence: «распозналось плохо». Это единственное
        место, где сервис говорит про качество снимка — в GET /payers поля нет,
        так что второго шанса его увидеть не будет.
        """
        path = _API_PREFIX + f"/v1/integration/checkout/payers/{self._path_phone(phone)}/documents"
        headers = self._sign("POST", path, "")
        data = {"doc_type": doc_type}
        if payer_ip:
            data["payer_ip"] = payer_ip
        return self._perform(
            "POST",
            self._base_url + path,
            headers=headers,
            data=data,
            files={"file": (filename, file, content_type)},
        )


def get_client() -> AlfabitClient | None:
    """Клиент по настройкам. None — ключи не заданы, оплата недоступна."""
    if not (settings.ALFABIT_API_KEY and settings.ALFABIT_SECRET_KEY):
        return None
    return AlfabitClient(
        settings.ALFABIT_API_KEY, settings.ALFABIT_SECRET_KEY, settings.ALFABIT_BASE_URL
    )
