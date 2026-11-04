import re

from django.conf import settings
from django.core.validators import FileExtensionValidator
from rest_framework import serializers

from .models import Category, Order, OrderItem, Product, StockMovement


def normalize_phone(value):
    """Accepts 01012345678, +201012345678, 00201012345678 (spaces/dashes ok) -> 01012345678."""
    v = re.sub(r"[\s\-()]", "", str(value))
    if v.startswith("+20"):
        v = "0" + v[3:]
    elif v.startswith("0020"):
        v = "0" + v[4:]
    elif v.startswith("20") and len(v) == 12:
        v = "0" + v[2:]
    if not re.fullmatch(r"01[0125]\d{8}", v):
        raise serializers.ValidationError("Enter a valid Egyptian mobile number, e.g. 01012345678.")
    return v


# ------------------------------------------------------------ public
class PublicCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name_en", "name_ar"]


class PublicProductSerializer(serializers.ModelSerializer):
    category_name_en = serializers.CharField(source="category.name_en", default="", read_only=True)
    category_name_ar = serializers.CharField(source="category.name_ar", default="", read_only=True)
    in_stock = serializers.SerializerMethodField()
    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "category", "category_name_en", "category_name_ar", "name_en", "name_ar",
                  "description_en", "description_ar", "price", "image", "featured",
                  "in_stock", "available_quantity"]

    def get_in_stock(self, obj):
        return obj.stock > 0

    def get_available_quantity(self, obj):
        return min(obj.stock, 99)  # never reveal exact warehouse numbers


class CheckoutItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class CheckoutSerializer(serializers.Serializer):
    idempotency_key = serializers.UUIDField()
    customer_name = serializers.CharField(max_length=120)
    customer_phone = serializers.CharField(max_length=30)
    notes = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices)
    payment_reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    items = CheckoutItemSerializer(many=True, allow_empty=False, max_length=50)

    def validate_customer_name(self, v):
        v = v.strip()
        if not v:
            raise serializers.ValidationError("Name is required.")
        return v

    def validate_customer_phone(self, v):
        return normalize_phone(v)


class TrackItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["product_name_en", "product_name_ar", "quantity", "unit_price", "line_total"]


class TrackSerializer(serializers.ModelSerializer):
    """What a customer may see. No phone number, no internal ids."""
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    items = TrackItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["reference", "status", "status_display", "rejection_reason", "payment_method",
                  "payment_method_display", "payment_status", "payment_status_display", "total",
                  "items", "created_at", "status_changed_at"]


# ------------------------------------------------------------ admin
class AdminCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name_en", "name_ar", "sort_order", "active", "product_count"]


class AdminProductSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)
    image = serializers.ImageField(
        required=False, allow_null=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )

    class Meta:
        model = Product
        fields = ["id", "category", "sku", "barcode", "name_en", "name_ar", "description_en",
                  "description_ar", "price", "stock", "low_stock_threshold", "image", "active",
                  "featured", "is_low_stock", "updated_at"]
        read_only_fields = ["updated_at"]
        extra_kwargs = {"sku": {"allow_null": True, "required": False, "allow_blank": True},
                        "barcode": {"allow_null": True, "required": False, "allow_blank": True}}

    def validate_sku(self, v):
        return v.strip() or None if v else None

    def validate_barcode(self, v):
        return v.strip() or None if v else None

    def validate_price(self, v):
        if v <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return v

    def validate_image(self, f):
        if f and f.size > settings.MAX_PRODUCT_IMAGE_BYTES:
            raise serializers.ValidationError("Image is too large (max 3 MB).")
        return f

    def validate(self, attrs):
        if self.instance is not None and "stock" in attrs and attrs["stock"] != self.instance.stock:
            raise serializers.ValidationError(
                {"stock": "Stock can only be changed with the adjust-stock action, so it is recorded."})
        return attrs


class StockAdjustSerializer(serializers.Serializer):
    delta = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=[StockMovement.Reason.RESTOCK, StockMovement.Reason.CORRECTION,
                                              StockMovement.Reason.DAMAGE])
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name_en", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", default="", read_only=True)

    class Meta:
        model = StockMovement
        fields = ["id", "product", "product_name", "delta", "stock_after", "reason", "order", "note",
                  "created_by_name", "created_at"]


class AdminOrderSerializer(serializers.ModelSerializer):
    items = TrackItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    handled_by_name = serializers.CharField(source="handled_by.username", default="", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "reference", "customer_name", "customer_phone", "notes", "status", "status_display",
                  "rejection_reason", "payment_method", "payment_method_display", "payment_status",
                  "payment_status_display", "payment_reference", "payment_confirmed_at", "total", "items",
                  "handled_by_name", "created_at", "status_changed_at", "updated_at"]


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
