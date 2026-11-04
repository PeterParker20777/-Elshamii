import hashlib
import hmac
import logging
import os
from datetime import timedelta

from django.db import connection, transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status as http
from rest_framework import viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import BootstrapState, Category, Order, Product, StockMovement
from .throttles import ClientScopedThrottle
from .serializers import (AdminCategorySerializer, AdminOrderSerializer, AdminProductSerializer,
                          CheckoutSerializer, PublicCategorySerializer, PublicProductSerializer,
                          StatusChangeSerializer, StockAdjustSerializer, StockMovementSerializer,
                          TrackSerializer)

log = logging.getLogger(__name__)


def service_error_response(exc):
    return Response({"error": exc.code, "detail": exc.message}, status=exc.http_status)


def health(request):
    """Public liveness check. Reveals nothing except up/down."""
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        return JsonResponse({"status": "ok", "database": "ok"})
    except Exception:
        log.exception("health check: database unavailable")
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)


# ====================================================== public (no login)
class PublicCategoryList(ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PublicCategorySerializer
    pagination_class = None
    queryset = Category.objects.filter(active=True)


class PublicProductList(ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PublicProductSerializer

    def get_queryset(self):
        qs = Product.objects.filter(active=True).select_related("category")
        p = self.request.query_params
        if p.get("category", "").isdigit():
            qs = qs.filter(category_id=int(p["category"]))
        if p.get("featured") == "1":
            qs = qs.filter(featured=True)
        q = p.get("q", "").strip()
        if q:
            qs = qs.filter(Q(name_en__icontains=q) | Q(name_ar__icontains=q))
        return qs


class PublicOrderCreate(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "public_order"

    def post(self, request):
        ser = CheckoutSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            order, created = services.create_order(
                idempotency_key=d["idempotency_key"], customer_name=d["customer_name"],
                customer_phone=d["customer_phone"], notes=d["notes"], payment_method=d["payment_method"],
                payment_reference=d["payment_reference"], items=d["items"])
        except services.ServiceError as exc:
            return service_error_response(exc)
        if created:
            log.info("order created %s", order.reference)  # reference only, no personal data
        # Only reached after the order is committed to the database.
        return Response({
            "reference": order.reference,
            "tracking_token": order.tracking_token,
            "tracking_url": f"/track/{order.tracking_token}/",
            "status": order.status,
            "total": str(order.total),
            "duplicate": not created,
        }, status=http.HTTP_201_CREATED if created else http.HTTP_200_OK)


class PublicOrderTrack(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "public_track"

    def get(self, request, token):
        try:
            order = Order.objects.prefetch_related("items").get(tracking_token=token)
        except Order.DoesNotExist:
            return Response({"error": "not_found", "detail": "Order not found."}, status=404)
        return Response(TrackSerializer(order).data)


# ====================================================== staff authentication
class LoginView(ObtainAuthToken):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "login"
    # ObtainAuthToken disables throttling by default, so enable it explicitly.
    throttle_classes = [ClientScopedThrottle]

    def post(self, request, *args, **kwargs):
        ser = self.serializer_class(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user = ser.validated_data["user"]
        if not user.is_staff:
            return Response({"error": "forbidden", "detail": "This account is not allowed to manage the store."},
                            status=403)
        token, _ = Token.objects.get_or_create(user=user)
        log.info("staff login: %s", user.username)
        return Response({"token": token.key, "username": user.username, "is_admin": user.is_superuser})


class BootstrapStatusView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        User = get_user_model()
        state = BootstrapState.objects.filter(pk=1).first()
        completed = bool(state and state.completed) or User.objects.filter(is_staff=True).exists()
        return Response({"setup_required": not completed})


class BootstrapOwnerView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "login"
    throttle_classes = [ClientScopedThrottle]

    def post(self, request):
        code = str(request.data.get("developer_code", ""))
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))
        configured_hash = os.getenv("ELSHAMII_DEVELOPER_CODE_HASH", "").strip()
        if not configured_hash:
            return Response({"error": "bootstrap_not_configured", "detail": "Developer activation is not configured on this installation."}, status=503)
        if not code or not username or len(username) > 150 or len(password) < 8:
            return Response({"error": "invalid_input", "detail": "Enter a username, a password of at least 8 characters, and the developer code."}, status=400)
        try:
            salt, expected = configured_hash.split("$", 1)
        except ValueError:
            return Response({"error": "bootstrap_not_configured", "detail": "Developer activation configuration is invalid."}, status=503)
        actual = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt.encode("utf-8"), 310000).hex()
        if not hmac.compare_digest(actual, expected):
            return Response({"error": "invalid_code", "detail": "Developer code is incorrect."}, status=403)

        User = get_user_model()
        candidate = User(username=username)
        try:
            validate_password(password, user=candidate)
            User._meta.get_field("username").run_validators(username)
        except ValidationError as exc:
            return Response({"error": "invalid_input", "detail": " ".join(exc.messages)}, status=400)
        try:
            with transaction.atomic():
                state, _ = BootstrapState.objects.get_or_create(pk=1)
                state = BootstrapState.objects.select_for_update().get(pk=1)
                if state.completed or User.objects.filter(is_staff=True).exists():
                    return Response({"error": "setup_completed", "detail": "The first owner account has already been created."}, status=409)
                if User.objects.filter(username=username).exists():
                    return Response({"error": "username_taken", "detail": "This username is already in use."}, status=409)
                user = User.objects.create_superuser(username=username, password=password)
                state.completed = True
                state.completed_at = timezone.now()
                state.save(update_fields=["completed", "completed_at"])
                token, _ = Token.objects.get_or_create(user=user)
        except Exception:
            log.exception("first owner bootstrap failed")
            return Response({"error": "bootstrap_failed", "detail": "Could not create the owner account."}, status=500)
        return Response({"token": token.key, "username": user.username, "is_admin": True}, status=201)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.auth:
            request.auth.delete()
        return Response(status=http.HTTP_204_NO_CONTENT)


# ====================================================== staff API
class DashboardView(APIView):
    def get(self, request):
        today = timezone.localdate()
        products = Product.objects.filter(active=True)
        counts = dict(Order.objects.values_list("status").annotate(n=Count("id")))
        today_orders = Order.objects.filter(created_at__date=today)
        sales = today_orders.exclude(status__in=[Order.Status.REJECTED, Order.Status.CANCELLED]) \
            .aggregate(s=Sum("total"))["s"] or 0
        return Response({
            "products": {
                "total": Product.objects.count(),
                "available": products.filter(stock__gt=0).count(),
                "low_stock": products.filter(stock__gt=0, stock__lte=F("low_stock_threshold")).count(),
                "out_of_stock": products.filter(stock=0).count(),
            },
            "orders": {s.value: counts.get(s.value, 0) for s in Order.Status},
            "today": {"orders": today_orders.count(), "sales": str(sales)},
        })


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = AdminCategorySerializer
    queryset = Category.objects.all()
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        cat = self.get_object()
        if cat.products.exists():
            return Response({"error": "category_in_use",
                              "detail": "This category has products. Move them or deactivate the category."},
                            status=409)
        return super().destroy(request, *args, **kwargs)


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = AdminProductSerializer

    def get_queryset(self):
        qs = Product.objects.select_related("category")
        p = self.request.query_params
        q = p.get("q", "").strip()
        if q:
            qs = qs.filter(Q(name_en__icontains=q) | Q(name_ar__icontains=q) | Q(sku__iexact=q)
                           | Q(barcode__iexact=q))
        if p.get("category", "").isdigit():
            qs = qs.filter(category_id=int(p["category"]))
        if p.get("active") in ("0", "1"):
            qs = qs.filter(active=p["active"] == "1")
        if p.get("low_stock") == "1":
            qs = qs.filter(stock__gt=0, stock__lte=F("low_stock_threshold"))
        if p.get("out_of_stock") == "1":
            qs = qs.filter(stock=0)
        return qs

    def perform_create(self, serializer):
        from django.db import transaction
        with transaction.atomic():
            product = serializer.save()
            if product.stock > 0:
                StockMovement.objects.create(product=product, delta=product.stock, stock_after=product.stock,
                                             reason=StockMovement.Reason.INITIAL, created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Products are never deleted (order history depends on them); they are deactivated."""
        product = self.get_object()
        product.active = False
        product.save(update_fields=["active", "updated_at"])
        return Response(self.get_serializer(product).data)

    @action(detail=True, methods=["post"], url_path="adjust-stock")
    def adjust_stock(self, request, pk=None):
        ser = StockAdjustSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            product = services.adjust_stock(int(pk), ser.validated_data["delta"], ser.validated_data["reason"],
                                            request.user, ser.validated_data["note"])
        except services.ServiceError as exc:
            return service_error_response(exc)
        return Response(self.get_serializer(product).data)


class StockMovementList(ListAPIView):
    serializer_class = StockMovementSerializer

    def get_queryset(self):
        qs = StockMovement.objects.select_related("product", "created_by")
        pid = self.request.query_params.get("product", "")
        return qs.filter(product_id=int(pid)) if pid.isdigit() else qs


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AdminOrderSerializer

    def get_queryset(self):
        qs = Order.objects.prefetch_related("items").select_related("handled_by")
        p = self.request.query_params
        if p.get("status") in Order.Status.values:
            qs = qs.filter(status=p["status"])
        q = p.get("q", "").strip()
        if q:
            qs = qs.filter(Q(reference__icontains=q) | Q(customer_name__icontains=q)
                           | Q(customer_phone__icontains=q))
        if p.get("after_id", "").isdigit():  # desktop polling: only orders newer than the last one seen
            qs = qs.filter(id__gt=int(p["after_id"]))
        return qs

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        ser = StatusChangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            order = services.change_status(int(pk), ser.validated_data["status"], request.user,
                                           ser.validated_data["reason"])
        except services.ServiceError as exc:
            return service_error_response(exc)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], url_path="confirm-payment")
    def confirm_payment(self, request, pk=None):
        try:
            order = services.confirm_payment(int(pk), request.user)
        except services.ServiceError as exc:
            return service_error_response(exc)
        return Response(self.get_serializer(order).data)
