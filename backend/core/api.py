from django.http import JsonResponse
from django.utils import timezone


def health(request):
    """Пульс бэкенда. Nuxt дёргает его при SSR — это доказывает, что именно
    серверный рендеринг видит Django по внутренней сети, а не только браузер."""
    return JsonResponse(
        {
            "status": "ok",
            "service": "enduro-backend",
            "time": timezone.now().isoformat(),
        }
    )
