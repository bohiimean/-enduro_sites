import secrets

from fastapi import Header, HTTPException, status

from . import config


def require_token(authorization: str = Header(default="")) -> None:
    """Bearer-токен. Сервис наружу не публикуется, но канал идёт через границу,
    так что голым его оставлять нельзя.

    Сравнение через compare_digest — чтобы по времени ответа токен не подбирался
    посимвольно."""
    if not config.TOKEN:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "RATE_SERVICE_TOKEN не задан — сервис отказывается отвечать",
        )
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(value, config.TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный токен")
