from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import MarkupRule, PaymentMethod, PricingSettings, RateQuote, RateSource
from .forms import MarkupRuleForm


class MarkupRuleInline(TabularInline):
    model = MarkupRule
    form = MarkupRuleForm
    extra = 0
    fields = ("label", "kind", "value", "threshold_rub", "weekdays", "time_from", "time_to",
              "is_active", "sort")


@admin.register(RateSource)
class RateSourceAdmin(ModelAdmin):
    list_display = ("code", "title", "is_active", "last_value", "last_fetched")
    list_filter = ("is_active",)
    search_fields = ("code", "title")

    @admin.display(description="последнее значение")
    def last_value(self, obj: RateSource):
        quote = obj.latest_quote
        return quote.value if quote else "—"

    @admin.display(description="получено")
    def last_fetched(self, obj: RateSource):
        quote = obj.latest_quote
        return quote.fetched_at if quote else "—"


@admin.register(RateQuote)
class RateQuoteAdmin(ModelAdmin):
    list_display = ("source", "value", "fetched_at", "created_at")
    list_filter = ("source",)
    date_hierarchy = "fetched_at"
    # Таблица append-only: руками сюда писать нечего.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PaymentMethod)
class PaymentMethodAdmin(ModelAdmin):
    list_display = ("title", "code", "source", "is_active", "sort")
    list_filter = ("is_active", "source")
    list_editable = ("sort", "is_active")
    inlines = [MarkupRuleInline]


@admin.register(MarkupRule)
class MarkupRuleAdmin(ModelAdmin):
    form = MarkupRuleForm
    list_display = ("method", "label", "kind_title", "value", "threshold_rub", "weekdays",
                    "time_from", "time_to", "is_active", "sort")
    list_filter = ("method", "kind", "is_active")
    list_editable = ("value", "is_active", "sort")

    def get_changelist_form(self, request, **kwargs):
        return super().get_changelist_form(request, form=MarkupRuleForm, **kwargs)

    @admin.display(description="тип наценки", ordering="kind")
    def kind_title(self, obj):
        return "Наценка в процентах (%)" if obj.kind == MarkupRule.KIND_MULTIPLIER else "Прибавка в рублях (₽)"


@admin.register(PricingSettings)
class PricingSettingsAdmin(ModelAdmin):
    list_display = ("__str__", "cny_divisor", "stale_after_minutes", "updated_at")

    def has_add_permission(self, request):
        return not PricingSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
