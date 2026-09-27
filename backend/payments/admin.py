from django.contrib import admin, messages
from django.utils import timezone

from .models import KycDocument, Payer, Payment


class KycDocumentInline(admin.TabularInline):
    model = KycDocument
    extra = 0
    fields = ("doc_type", "uploaded_by", "uploaded_at", "low_confidence", "consent_at")
    readonly_fields = fields
    can_delete = False


@admin.register(Payer)
class PayerAdmin(admin.ModelAdmin):
    list_display = ("phone", "kyc_status", "expected_payer_name", "processing",
                    "manual_review", "last_checked_at", "watch_since")
    list_filter = ("kyc_status", "processing", "manual_review")
    search_fields = ("phone", "expected_payer_name")
    readonly_fields = ("created_at", "updated_at")
    inlines = [KycDocumentInline]


class IssueFilter(admin.SimpleListFilter):
    """Главный список менеджера на этапе 5: оплачено, но юань ещё не выдан.
    Пока уведомления в Telegram нет, это и есть уведомление."""

    title = "выдача юаня"
    parameter_name = "issue"

    def lookups(self, request, model_admin):
        return [("todo", "К выдаче"), ("done", "Выдано")]

    def queryset(self, request, queryset):
        if self.value() == "todo":
            return queryset.filter(status=Payment.STATUS_PAID, issued_at__isnull=True)
        if self.value() == "done":
            return queryset.filter(issued_at__isnull=False)
        return queryset


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("external_payment_id", "user", "phone", "amount_rub", "amount_cny",
                    "price_per_cny", "status", "paid_at", "issued_at", "created_at")
    list_filter = (IssueFilter, "status", "created_at")
    search_fields = ("external_payment_id", "payment_uid", "phone", "user__email")
    autocomplete_fields = ("user",)
    readonly_fields = (
        "external_payment_id", "payment_uid", "user", "payer", "phone",
        "amount_cny", "amount_rub", "rate_used", "price_per_cny",
        "status", "provider_status", "qr_url", "qr_payload",
        "payer_ip", "payer_user_agent", "raw_response",
        "created_at", "paid_at", "last_checked_at", "issued_at", "issued_by",
    )
    actions = ["mark_issued"]

    # Платежи заводит только код: руками такую запись не создать корректно.
    def has_add_permission(self, request):
        return False

    @admin.action(description="Юань выдан")
    def mark_issued(self, request, queryset):
        # Только оплаченные и ещё не выданные — случайный клик по неоплаченному
        # не должен выглядеть как выдача.
        done = queryset.filter(status=Payment.STATUS_PAID, issued_at__isnull=True).update(
            issued_at=timezone.now(), issued_by=request.user
        )
        skipped = queryset.count() - done
        self.message_user(request, f"Отмечено выданными: {done}.")
        if skipped:
            self.message_user(
                request, f"Пропущено {skipped}: не оплачены или уже выданы.", messages.WARNING
            )

    def changelist_view(self, request, extra_context=None):
        todo = Payment.objects.filter(status=Payment.STATUS_PAID, issued_at__isnull=True).count()
        if todo and "issue" not in request.GET:
            self.message_user(
                request,
                f"Оплачено и ждёт выдачи юаня: {todo}. Фильтр «Выдача юаня → К выдаче».",
                messages.WARNING,
            )
        return super().changelist_view(request, extra_context)


@admin.register(KycDocument)
class KycDocumentAdmin(admin.ModelAdmin):
    list_display = ("payer", "doc_type", "uploaded_by", "uploaded_at", "low_confidence")
    list_filter = ("doc_type", "low_confidence")
    search_fields = ("payer__phone",)
    readonly_fields = ("payer", "doc_type", "uploaded_by", "consent_at", "uploaded_at",
                       "low_confidence", "response")

    def has_add_permission(self, request):
        return False
