from django.contrib import admin

from .models import Category, Order, OrderItem, Product, StockMovement


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "sort_order", "active")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ar", "category", "price", "stock", "active")
    list_filter = ("active", "category")
    search_fields = ("name_en", "name_ar", "sku", "barcode")
    readonly_fields = ("stock",)  # change stock through the API so it is recorded


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "product_name_en", "product_name_ar", "quantity", "unit_price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer_name", "total", "status", "payment_status", "created_at")
    list_filter = ("status", "payment_method", "payment_status")
    search_fields = ("reference", "customer_name", "customer_phone")
    # status is read-only here: use the desktop app so stock and history stay consistent
    readonly_fields = ("reference", "tracking_token", "idempotency_key", "total", "stock_deducted", "status")
    inlines = [OrderItemInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("product", "delta", "stock_after", "reason", "created_by", "created_at")
    readonly_fields = [f.name for f in StockMovement._meta.fields]
