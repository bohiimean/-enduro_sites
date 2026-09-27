"""API кабинета: профиль и номера телефона.

Доступ закрыт по умолчанию — в проекте стоит `IsAuthenticated` в настройках
DRF, поэтому здесь `permission_classes` не повторяется. Все выборки идут от
`request.user`; телефон из запроса ничего не открывает.
"""
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from .models import PhoneNumber
from .serializers import PhoneNumberSerializer, ProfileSerializer


class PhoneTaken(APIException):
    """Номер занимает первый, кто его привязал.

    Забрать номер можно будет только подтверждением владения, когда на этапе 6
    появятся каналы (MAX / Telegram / SMS). Принятый риск описан в модели
    `PhoneNumber`: занявший чужой номер не видит ни ФИО по паспорту, ни заказов.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Этот номер уже привязан к другому аккаунту."
    default_code = "phone_taken"


class ProfileView(generics.RetrieveUpdateAPIView):
    """Профиль текущего пользователя. Правится только ФИО."""

    serializer_class = ProfileSerializer

    def get_object(self):
        return self.request.user


class PhoneListCreateView(generics.ListCreateAPIView):
    serializer_class = PhoneNumberSerializer
    # Постраничность тут только мешает: номеров у человека один-два, а фронту
    # удобнее получить простой список.
    pagination_class = None

    def get_queryset(self):
        return self.request.user.phones.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        existing = PhoneNumber.objects.filter(phone=phone).first()
        if existing:
            if existing.user_id != request.user.pk:
                raise PhoneTaken()
            # Свой же номер: повторная привязка — не ошибка, отдаём как есть.
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)

        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PhoneDestroyView(generics.DestroyAPIView):
    """Отвязка номера. Своего — можно всегда, чужой сюда не попадёт: выборка
    ограничена номерами текущего пользователя."""

    serializer_class = PhoneNumberSerializer

    def get_queryset(self):
        return self.request.user.phones.all()
