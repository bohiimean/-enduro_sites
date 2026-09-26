from rest_framework import serializers


class TierSerializer(serializers.Serializer):
    label = serializers.CharField()
    threshold_rub = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    price_per_cny = serializers.DecimalField(max_digits=12, decimal_places=2)


class MethodPriceSerializer(serializers.Serializer):
    code = serializers.CharField()
    title = serializers.CharField()
    subtitle = serializers.CharField()
    note = serializers.CharField()
    source_code = serializers.CharField()
    available = serializers.BooleanField()
    rate = serializers.DecimalField(max_digits=18, decimal_places=6, allow_null=True)
    fetched_at = serializers.DateTimeField(allow_null=True)
    is_stale = serializers.BooleanField()
    tiers = TierSerializer(many=True)


class ShowcaseSerializer(serializers.Serializer):
    divisor = serializers.DecimalField(max_digits=8, decimal_places=4)
    generated_at = serializers.DateTimeField()
    methods = MethodPriceSerializer(many=True)
