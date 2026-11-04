import secrets

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

_REF_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def generate_reference():
    return "PP-" + "".join(secrets.choice(_REF_ALPHABET) for _ in range(8))


def generate_tracking_token():
    return secrets.token_urlsafe(24)


class Category(models.Model):
    name_en = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name_en"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name_en


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    sku = models.CharField(max_length=50, unique=True, null=True, blank=True)
    barcode = models.CharField(max_length=64, unique=True, null=True, blank=True)
    name_en = models.CharField(max_length=160)
    name_ar = models.CharField(max_length=160)
    description_en = models.TextField(blank=True)
    description_ar = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    active = models.BooleanField(default=True)  # products are deactivated, never deleted
    featured = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name_en"]

    def __str__(self):
        return self.name_en

    @property
    def is_low_stock(self):
        return 0 < self.stock <= self.low_stock_threshold


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        INITIAL = "INITIAL", "Initial stock"
        RESTOCK = "RESTOCK", "Restock"
        CORRECTION = "CORRECTION", "Correction"
        DAMAGE = "DAMAGE", "Damaged / expired"
        ORDER_ACCEPTED = "ORDER_ACCEPTED", "Order accepted"
        ORDER_CANCELLED = "ORDER_CANCELLED", "Order cancelled (restored)"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    delta = models.IntegerField()
    stock_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    order = models.ForeignKey("Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="movements")
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        PREPARING = "PREPARING", "Preparing"
        READY = "READY", "Ready for pickup"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash on pickup"
        INSTAPAY = "INSTAPAY", "InstaPay"
        VODAFONE_CASH = "VODAFONE_CASH", "Vodafone Cash"
        ORANGE_CASH = "ORANGE_CASH", "Orange Cash"
        WE_CASH = "WE_CASH", "WE Cash"

    class PaymentStatus(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid (pay at pickup)"
        AWAITING_VERIFICATION = "AWAITING_VERIFICATION", "Awaiting manual verification"
        CONFIRMED = "CONFIRMED", "Payment confirmed"

    # Human-friendly number shown to staff and customer. NOT a secret.
    reference = models.CharField(max_length=14, unique=True, default=generate_reference, editable=False)
    # Secret used by the customer to track the order. Never sequential.
    tracking_token = models.CharField(max_length=64, unique=True, default=generate_tracking_token, editable=False)
    # Sent by the browser once per checkout attempt; makes retries safe.
    idempotency_key = models.UUIDField(unique=True)

    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=20)
    notes = models.CharField(max_length=300, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.CharField(max_length=300, blank=True)
    payment_method = models.CharField(max_length=14, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    payment_status = models.CharField(max_length=24, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    payment_reference = models.CharField(max_length=100, blank=True)  # e.g. sender phone / transfer ref. Never PINs.
    payment_confirmed_at = models.DateTimeField(null=True, blank=True)
    payment_confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                             blank=True, related_name="+")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_deducted = models.BooleanField(default=False)

    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    status_changed_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    product_name_en = models.CharField(max_length=160)
    product_name_ar = models.CharField(max_length=160)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return self.quantity * self.unit_price


class BootstrapState(models.Model):
    """Singleton lock recording whether the first owner account was created."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "installation bootstrap state"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "First owner created" if self.completed else "First owner setup pending"
