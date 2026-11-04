"""All business rules live here, so the API, the admin and the tests share them."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Order, OrderItem, Product, StockMovement

S = Order.Status
MAX_QTY_PER_LINE = 99
MAX_LINES = 50

ALLOWED_TRANSITIONS = {
    S.PENDING: {S.ACCEPTED, S.REJECTED, S.CANCELLED},
    S.ACCEPTED: {S.PREPARING, S.CANCELLED},
    S.PREPARING: {S.READY, S.CANCELLED},
    S.READY: {S.COMPLETED, S.CANCELLED},
    S.COMPLETED: set(),
    S.REJECTED: set(),
    S.CANCELLED: set(),
}


class ServiceError(Exception):
    def __init__(self, code, message, http_status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


# ---------------------------------------------------------------- stock
def _move(product, delta, reason, user=None, order=None, note=""):
    """Apply a stock change to an already-locked product and record it."""
    new_stock = product.stock + delta
    if new_stock < 0:
        raise ServiceError("insufficient_stock", f"Not enough stock for {product.name_en}.", 409)
    product.stock = new_stock
    product.save(update_fields=["stock", "updated_at"])
    StockMovement.objects.create(product=product, delta=delta, stock_after=new_stock, reason=reason,
                                 order=order, note=note[:200], created_by=user)


def adjust_stock(product_id, delta, reason, user, note=""):
    if delta == 0:
        raise ServiceError("invalid_delta", "Change must not be zero.")
    allowed = {StockMovement.Reason.RESTOCK, StockMovement.Reason.CORRECTION, StockMovement.Reason.DAMAGE}
    if reason not in allowed:
        raise ServiceError("invalid_reason", "Invalid reason for a manual stock change.")
    with transaction.atomic():
        try:
            product = Product.objects.select_for_update().get(pk=product_id)
        except Product.DoesNotExist:
            raise ServiceError("not_found", "Product not found.", 404)
        _move(product, delta, reason, user=user, note=note)
    return product


# ---------------------------------------------------------------- orders
def create_order(*, idempotency_key, customer_name, customer_phone, notes, payment_method,
                 payment_reference, items):
    """Create a pickup order from a customer checkout.

    Prices always come from the database. Calling this twice with the same
    idempotency_key returns the first order instead of creating a duplicate.
    Stock is validated here but only deducted when staff accept the order.
    """
    existing = Order.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing, False

    if not items or len(items) > MAX_LINES:
        raise ServiceError("invalid_items", "Cart must contain between 1 and 50 products.")

    wanted = {}
    for row in items:
        wanted[row["product_id"]] = wanted.get(row["product_id"], 0) + row["quantity"]

    try:
        with transaction.atomic():
            products = {p.id: p for p in Product.objects.filter(id__in=wanted.keys(), active=True)}
            total = Decimal("0.00")
            lines = []
            for pid, qty in wanted.items():
                product = products.get(pid)
                if product is None:
                    raise ServiceError("product_unavailable", "A product in your cart is no longer available.", 409)
                if qty > MAX_QTY_PER_LINE:
                    raise ServiceError("invalid_items", "Quantity too large.")
                if product.stock < qty:
                    raise ServiceError("insufficient_stock",
                                       f"Only {product.stock} left of {product.name_en}.", 409)
                total += product.price * qty
                lines.append((product, qty))

            wallet = payment_method != Order.PaymentMethod.CASH
            order = Order.objects.create(
                idempotency_key=idempotency_key,
                customer_name=customer_name, customer_phone=customer_phone, notes=notes,
                payment_method=payment_method, payment_reference=payment_reference if wallet else "",
                payment_status=(Order.PaymentStatus.AWAITING_VERIFICATION if wallet
                                else Order.PaymentStatus.UNPAID),
                total=total,
            )
            OrderItem.objects.bulk_create([
                OrderItem(order=order, product=p, product_name_en=p.name_en, product_name_ar=p.name_ar,
                          quantity=q, unit_price=p.price) for p, q in lines
            ])
    except IntegrityError:
        # Two identical requests raced; return the winner.
        existing = Order.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing, False
        raise ServiceError("conflict", "Could not save the order. Please try again.", 503)
    return order, True


def change_status(order_id, new_status, user, reason=""):
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id)
        except Order.DoesNotExist:
            raise ServiceError("not_found", "Order not found.", 404)

        if new_status not in ALLOWED_TRANSITIONS[order.status]:
            raise ServiceError("invalid_transition",
                               f"Cannot change order from {order.status} to {new_status}.", 409)
        if new_status == S.REJECTED and not reason.strip():
            raise ServiceError("reason_required", "A reason is required to reject an order.")

        items = list(order.items.select_related("product").order_by("product_id"))

        if new_status == S.ACCEPTED:
            locked = {p.id: p for p in Product.objects.select_for_update()
                      .filter(id__in=[i.product_id for i in items]).order_by("id")}
            for i in items:
                _move(locked[i.product_id], -i.quantity, StockMovement.Reason.ORDER_ACCEPTED,
                      user=user, order=order, note=order.reference)
            order.stock_deducted = True

        if new_status == S.CANCELLED and order.stock_deducted:
            locked = {p.id: p for p in Product.objects.select_for_update()
                      .filter(id__in=[i.product_id for i in items]).order_by("id")}
            for i in items:
                _move(locked[i.product_id], i.quantity, StockMovement.Reason.ORDER_CANCELLED,
                      user=user, order=order, note=order.reference)
            order.stock_deducted = False

        if new_status in (S.REJECTED, S.CANCELLED):
            order.rejection_reason = reason.strip()[:300]

        if new_status == S.COMPLETED and order.payment_method == Order.PaymentMethod.CASH:
            order.payment_status = Order.PaymentStatus.CONFIRMED
            order.payment_confirmed_at = timezone.now()
            order.payment_confirmed_by = user

        order.status = new_status
        order.status_changed_at = timezone.now()
        order.handled_by = user
        order.save()
    return order


def confirm_payment(order_id, user):
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id)
        except Order.DoesNotExist:
            raise ServiceError("not_found", "Order not found.", 404)
        if order.status in (S.REJECTED, S.CANCELLED):
            raise ServiceError("invalid_state", "This order is closed.", 409)
        if order.payment_status == Order.PaymentStatus.CONFIRMED:
            return order
        order.payment_status = Order.PaymentStatus.CONFIRMED
        order.payment_confirmed_at = timezone.now()
        order.payment_confirmed_by = user
        order.save()
    return order
