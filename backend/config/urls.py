from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.api import health

urlpatterns = [
    path("admin/", admin.site.urls),
    # Вход, регистрация, подтверждение почты и сброс пароля.
    # Путь оставлен ровно таким, какой у allauth по умолчанию, и не переклеен
    # под /api/v1/auth/ — чтобы примеры из документации совпадали один в один.
    # В nginx для него есть отдельная location: иначе запрос уехал бы в Nuxt.
    path("_allauth/", include("allauth.headless.urls")),
    path("api/v1/health/", health, name="health"),
    path("api/v1/account/", include("accounts.urls")),
    path("api/v1/catalog/", include("catalog.urls")),
    path("api/v1/pricing/", include("pricing.urls")),
    path("api/v1/payments/", include("payments.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Enduro — управление"
admin.site.site_title = "Enduro"
admin.site.index_title = "Разделы"
