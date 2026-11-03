from django.contrib import admin, messages
from unfold.admin import ModelAdmin, TabularInline

from .models import Order, OrderPhone, PurchaseRequest, PurchaseRequestItem, SupplyStatus


@admin.register(SupplyStatus)
class SupplyStatusAdmin(ModelAdmin):
    list_display = ("name", "sort", "is_final")
    list_editable = ("sort", "is_final")


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ("id", "title", "color", "quantity", "phone", "full_name", "city", "price",
                    "paid", "remainder_display", "supply_status", "ordered_at")
    list_filter = ("supply_status", "city", "ordered_at")
    search_fields = ("phone", "full_name", "product_title", "external_key", "comment")
    autocomplete_fields = ("user", "product")
    date_hierarchy = "ordered_at"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Клиент", {
            "fields": ("phone", "full_name", "city", "delivery_company", "user"),
            "description": "Клиент видит заказ в кабинете по номеру, который указал "
                           "во вкладке «Заказы». Поле «клиент» — чтобы показать заказ "
                           "аккаунту с другим номером.",
        }),
        ("Позиция", {"fields": ("product", "product_title", "color", "quantity")}),
        ("Деньги", {"fields": ("price", "paid")}),
        ("Поставка", {"fields": ("supply_status", "ordered_at", "comment")}),
        ("Служебное", {"fields": ("external_key", "created_at", "updated_at")}),
    )

    @admin.display(description="остаток, ₽")
    def remainder_display(self, obj: Order):
        return obj.remainder


class ChangeRequestFilter(admin.SimpleListFilter):
    title = "смена номера"
    parameter_name = "request"

    def lookups(self, request, model_admin):
        return [("pending", "Ждёт решения")]

    def queryset(self, request, queryset):
        if self.value() == "pending":
            return queryset.exclude(requested_phone="")
        return queryset


@admin.register(OrderPhone)
class OrderPhoneAdmin(ModelAdmin):
    """Номер для заказов человек сам сменить не может — только заявкой сюда.
    Прежде чем одобрять, убедиться, что номер его: заявка открывает чужие
    заказы так же, как первый ввод."""

    list_display = ("phone", "user", "requested_phone", "requested_at", "changed_at")
    list_filter = (ChangeRequestFilter,)
    search_fields = ("phone", "requested_phone", "user__email", "user__full_name")
    autocomplete_fields = ("user",)
    readonly_fields = ("requested_at", "created_at", "changed_at")
    actions = ["approve_change", "reject_change"]

    @admin.action(description="Одобрить смену номера")
    def approve_change(self, request, queryset):
        done = sum(phone.approve_change() for phone in queryset)
        skipped = queryset.count() - done
        self.message_user(request, f"Номер сменён: {done}.")
        if skipped:
            self.message_user(
                request,
                f"Пропущено {skipped}: заявки нет или новый номер уже занят другим аккаунтом.",
                messages.WARNING,
            )

    @admin.action(description="Отклонить смену номера")
    def reject_change(self, request, queryset):
        done = sum(phone.reject_change() for phone in queryset)
        self.message_user(request, f"Заявок отклонено: {done}.")

    def changelist_view(self, request, extra_context=None):
        pending = OrderPhone.objects.exclude(requested_phone="").count()
        if pending and "request" not in request.GET:
            self.message_user(
                request,
                f"Ждут смены номера: {pending}. Фильтр «Смена номера → Ждёт решения».",
                messages.WARNING,
            )
        return super().changelist_view(request, extra_context)


class PurchaseRequestItemInline(TabularInline):
    model = PurchaseRequestItem
    extra = 0
    can_delete = False
    fields = ("title", "offer", "quantity", "unit_price_rub")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(ModelAdmin):
    list_display = ("id", "name", "phone", "city", "payment_method", "status", "manager_note", "created_at")
    list_display_links = ("id", "name")
    list_editable = ("status",)
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("name", "phone", "city", "user__email", "items__title")
    readonly_fields = ("user", "name", "phone", "city", "payment_method", "created_at", "updated_at")
    fields = ("user", "name", "phone", "city", "payment_method", "status", "manager_note", "created_at", "updated_at")
    inlines = [PurchaseRequestItemInline]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False
