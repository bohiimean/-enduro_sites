from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ShowcaseSerializer
from .services import build_showcase


class PricingView(APIView):
    """Витрина курса. Считается из БД — за границу в запросе пользователя не
    ходим, котировки туда кладёт `worker`."""

    # Страница курса публичная, а по умолчанию API закрыто.
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(ShowcaseSerializer(build_showcase()).data)
