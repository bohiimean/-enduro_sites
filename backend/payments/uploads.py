"""Приём фото паспорта только в память.

Django по умолчанию держит в памяти файлы до 2.5 МБ, а всё, что больше, пишет
во временный файл на диске (`TemporaryFileUploadHandler`). Фото паспорта с
телефона — как раз 3–8 МБ, то есть без этого модуля паспорт лёг бы на наш диск
в обход гарантии «байты документов не храним» (CLAUDE.md, раздел 152-ФЗ).

Здесь остаётся один обработчик — в памяти, без порога. Размер ограничен
явно: запрос целиком не больше `MAX_REQUEST_BYTES`, каждый файл не больше
`MAX_FILE_BYTES`. Вторая половина той же гарантии — в nginx
(`proxy_request_buffering off` на этом пути), иначе тело запроса ложится на
диск ещё до Django.
"""
from django.core.files.uploadhandler import MemoryFileUploadHandler, StopUpload

# Бот пропускает до 20 МБ (предел getFile у Telegram), у alfabit предел 25 МБ.
MAX_FILE_BYTES = 20 * 1024 * 1024
# Два документа плюс поля формы.
MAX_REQUEST_BYTES = 2 * MAX_FILE_BYTES + 1024 * 1024


class InMemoryOnlyUploadHandler(MemoryFileUploadHandler):
    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        # Родитель включается, только если запрос меньше
        # FILE_UPLOAD_MAX_MEMORY_SIZE, а иначе отдаёт файл следующему
        # обработчику — временному файлу. Следующего здесь нет, поэтому
        # включаемся всегда, а размер проверяет view до разбора тела.
        self.activated = True

    def receive_data_chunk(self, raw_data, start):
        if start + len(raw_data) > MAX_FILE_BYTES:
            raise StopUpload(connection_reset=True)
        return super().receive_data_chunk(raw_data, start)


def memory_only(request) -> None:
    """Поставить обработчик. Вызывать до первого обращения к телу запроса."""
    request.upload_handlers = [InMemoryOnlyUploadHandler(request)]
