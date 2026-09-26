from django.contrib import admin

from .models import KycDocument, Payer, Payment


class KycDocumentInline(admin.TabularInline):
    model = KycDocument
    extra = 0
    fields = ("doc_type", "uploaded_at", "low_confidence")
    readonly_fields = ("doc_type", "uploaded_at", "low_confidence")
    can_delete = False


@admin.register(Payer)
class PayerAdmin(admin.ModelAdmin):
    list_display = ("phone", "kyc_status", "expected_payer_name", "processing",
                    "manual_review", "last_checked_at", "watch_since")
    list_filter = ("kyc_status", "processing", "manual_review")
    search_fields = ("phone", "expected_payer_name")
    readonly_fields = ("created_at", "updated_at")
    inlines = [KycDocumentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("external_payment_id", "phone", "amount_rub", "amount_cny",
                    "price_per_cny", "status", "created_at", "paid_at")
    list_filter = ("status", "created_at")
    search_fields = ("external_payment_id", "payment_uid", "phone")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "raw_response")

    # Платежи заводит только код: руками такую запись не создать корректно.
    def has_add_permission(self, request):
        return False


@admin.register(KycDocument)
class KycDocumentAdmin(admin.ModelAdmin):
    list_display = ("payer", "doc_type", "uploaded_at", "low_confidence")
    list_filter = ("doc_type", "low_confidence")
    search_fields = ("payer__phone",)

    def has_add_permission(self, request):
        return False
