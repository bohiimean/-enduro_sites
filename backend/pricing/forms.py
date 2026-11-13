from decimal import Decimal

from django import forms
from unfold.widgets import UnfoldAdminTextInputWidget

from .models import MarkupRule


class MarkupValueField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().removesuffix("%").strip().replace(",", ".")
        return super().to_python(value)


class MarkupRuleForm(forms.ModelForm):
    value = MarkupValueField(
        label="Значение, % или ₽",
        help_text="Для процентной наценки: 4,5 или 4,5%. Для прибавки в рублях: 2,6 без знака %.",
        widget=UnfoldAdminTextInputWidget(attrs={"inputmode": "decimal"}),
    )

    class Meta:
        model = MarkupRule
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "kind" in self.fields:
            self.fields["kind"].choices = [
                (MarkupRule.KIND_MULTIPLIER, "Наценка в процентах (%)"),
                (MarkupRule.KIND_RUB_ADD, "Прибавка в рублях (₽)"),
            ]
        # В БД остаётся коэффициент: старые данные и формулы не меняются.
        if self.instance.pk and self.instance.kind == MarkupRule.KIND_MULTIPLIER:
            self.initial["value"] = (self.instance.value - 1) * 100

    def clean_value(self):
        value = self.cleaned_data["value"]
        # В редактируемом списке тип отсутствует в форме, берём его из записи.
        kind = self.cleaned_data.get("kind", self.instance.kind)
        if kind == MarkupRule.KIND_MULTIPLIER:
            return (Decimal(1) + value / 100).normalize()
        raw = self.data.get(self.add_prefix("value"), "")
        if "%" in str(raw):
            raise forms.ValidationError("Для прибавки в рублях введите сумму без знака %.")
        return value.normalize()
