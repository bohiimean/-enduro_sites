from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from accounts.models import User
from .admin import MarkupRuleAdmin, PaymentMethodAdmin
from .forms import MarkupRuleForm
from .models import MarkupRule, PaymentMethod, RateSource


class MarkupFormTests(TestCase):
    def setUp(self):
        source = RateSource.objects.create(code="rapira", title="Rapira")
        self.method = PaymentMethod.objects.create(code="qr", title="QR", source=source)
        self.rule = MarkupRule.objects.create(
            method=self.method, label="Стандарт", kind="multiplier", value=Decimal("1.045")
        )
        self.data = {"method": self.method.pk, "label": "Стандарт", "kind": "multiplier",
                     "value": "4,5", "sort": "0", "is_active": "on"}

    def test_existing_value_is_displayed_in_percent_without_changing_price(self):
        self.assertEqual(MarkupRuleForm(instance=self.rule).initial["value"], Decimal("4.5"))
        for value in ("4,5", "4.5%", "4,5000 %", "4.5000"):
            form = MarkupRuleForm({**self.data, "value": value}, instance=self.rule)
            self.assertTrue(form.is_valid(), form.errors)
            rule = form.save()
            self.assertEqual(rule.value, Decimal("1.045"))
            self.assertEqual(rule.apply(Decimal("100")), Decimal("104.5"))

    def test_rubles_and_switching_type(self):
        form = MarkupRuleForm({**self.data, "kind": "rub_add", "value": "2,6"}, instance=self.rule)
        self.assertTrue(form.is_valid(), form.errors)
        rule = form.save()
        self.assertEqual(rule.apply(Decimal("100")), Decimal("102.6"))
        self.assertEqual(MarkupRuleForm(instance=rule).initial["value"], Decimal("2.6"))
        form = MarkupRuleForm({**self.data, "value": "10%"}, instance=rule)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().apply(Decimal("100")), Decimal("110"))

    def test_percent_sign_is_rejected_for_rubles(self):
        form = MarkupRuleForm({**self.data, "kind": "rub_add", "value": "2,6%"})
        self.assertFalse(form.is_valid())
        self.assertIn("без знака %", form.errors["value"][0])

    def test_zero_percent(self):
        form = MarkupRuleForm({**self.data, "value": "0"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().value, Decimal("1"))

    def test_admin_changelist_and_inline_use_percentage_form(self):
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser("manager@example.com", "password")
        admin = MarkupRuleAdmin(MarkupRule, AdminSite())
        formset = admin.get_changelist_formset(request)
        form = formset.form({"value": "4,5%", "sort": "0", "is_active": "on"}, instance=self.rule)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().value, Decimal("1.045"))
        inline = PaymentMethodAdmin(PaymentMethod, AdminSite()).get_inline_instances(request)[0]
        inline_form = inline.get_formset(request, self.method).form
        form = inline_form({**self.data, "value": "5%"}, instance=self.rule)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().value, Decimal("1.05"))
