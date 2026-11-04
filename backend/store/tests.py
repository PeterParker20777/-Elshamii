import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from .models import Category, Order, Product, StockMovement
from .services import ServiceError, change_status

User = get_user_model()


def checkout_payload(product_id, qty=2, **extra):
    data = {"idempotency_key": str(uuid.uuid4()), "customer_name": "Ali", "customer_phone": "01012345678",
            "payment_method": "CASH", "items": [{"product_id": product_id, "quantity": qty}]}
    data.update(extra)
    return data


class BaseCase(APITestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache; start every test clean
        self.staff = User.objects.create_user("staff", password="pw-12345-xyz", is_staff=True)
        self.cat = Category.objects.create(name_en="Dairy", name_ar="ألبان")
        self.milk = Product.objects.create(category=self.cat, name_en="Milk", name_ar="لبن", price="30.00", stock=10)

    def auth(self):
        self.client.force_authenticate(self.staff)


class PublicOrderTests(BaseCase):
    def test_price_comes_from_server(self):
        r = self.client.post("/api/public/orders/", checkout_payload(self.milk.id, 2, total="1.00"), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["total"], "60.00")

    def test_duplicate_checkout_returns_same_order(self):
        payload = checkout_payload(self.milk.id)
        r1 = self.client.post("/api/public/orders/", payload, format="json")
        r2 = self.client.post("/api/public/orders/", payload, format="json")
        self.assertEqual(r1.data["reference"], r2.data["reference"])
        self.assertEqual(Order.objects.count(), 1)
        self.assertTrue(r2.data["duplicate"])

    def test_insufficient_stock_rejected(self):
        r = self.client.post("/api/public/orders/", checkout_payload(self.milk.id, 11), format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Order.objects.count(), 0)

    def test_inactive_product_rejected(self):
        self.milk.active = False
        self.milk.save()
        r = self.client.post("/api/public/orders/", checkout_payload(self.milk.id), format="json")
        self.assertEqual(r.status_code, 409)

    def test_bad_phone_rejected(self):
        r = self.client.post("/api/public/orders/", checkout_payload(self.milk.id, customer_phone="123"),
                             format="json")
        self.assertEqual(r.status_code, 400)

    def test_wallet_order_awaits_verification(self):
        r = self.client.post("/api/public/orders/", checkout_payload(self.milk.id, payment_method="INSTAPAY"),
                             format="json")
        order = Order.objects.get(reference=r.data["reference"])
        self.assertEqual(order.payment_status, Order.PaymentStatus.AWAITING_VERIFICATION)

    def test_tracking_hides_phone_and_needs_token(self):
        r = self.client.post("/api/public/orders/", checkout_payload(self.milk.id), format="json")
        t = self.client.get(f"/api/public/orders/track/{r.data['tracking_token']}/")
        self.assertEqual(t.status_code, 200)
        self.assertNotIn("customer_phone", t.data)
        self.assertEqual(self.client.get("/api/public/orders/track/not-a-token/").status_code, 404)


    def test_order_endpoint_is_rate_limited(self):
        codes = [self.client.post("/api/public/orders/", checkout_payload(self.milk.id, 1), format="json").status_code
                 for _ in range(12)]
        self.assertIn(429, codes)


class StaffTests(BaseCase):
    def make_order(self, qty=3):
        r = self.client.post("/api/public/orders/", checkout_payload(self.milk.id, qty), format="json")
        return Order.objects.get(reference=r.data["reference"])

    def test_admin_api_requires_login(self):
        self.assertIn(self.client.get("/api/admin/orders/").status_code, (401, 403))
        self.assertIn(self.client.get("/api/admin/dashboard/").status_code, (401, 403))

    def test_non_staff_user_blocked(self):
        User.objects.create_user("cust", password="pw-12345-xyz")
        r = self.client.post("/api/auth/login/", {"username": "cust", "password": "pw-12345-xyz"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_staff_login_returns_token(self):
        r = self.client.post("/api/auth/login/", {"username": "staff", "password": "pw-12345-xyz"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.data)

    def test_accept_deducts_stock_and_logs_movement(self):
        order = self.make_order(3)
        change_status(order.id, "ACCEPTED", self.staff)
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.stock, 7)
        self.assertEqual(StockMovement.objects.filter(reason="ORDER_ACCEPTED").count(), 1)

    def test_cancel_after_accept_restores_stock(self):
        order = self.make_order(3)
        change_status(order.id, "ACCEPTED", self.staff)
        change_status(order.id, "CANCELLED", self.staff, "customer called")
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.stock, 10)

    def test_invalid_transition_blocked(self):
        order = self.make_order()
        with self.assertRaises(ServiceError):
            change_status(order.id, "COMPLETED", self.staff)

    def test_reject_requires_reason(self):
        order = self.make_order()
        with self.assertRaises(ServiceError):
            change_status(order.id, "REJECTED", self.staff, "")
        change_status(order.id, "REJECTED", self.staff, "out of delivery area")

    def test_full_happy_path_via_api(self):
        order = self.make_order(2)
        self.auth()
        for st in ("ACCEPTED", "PREPARING", "READY", "COMPLETED"):
            r = self.client.post(f"/api/admin/orders/{order.id}/status/", {"status": st}, format="json")
            self.assertEqual(r.status_code, 200, r.data)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.CONFIRMED)

    def test_stock_cannot_be_edited_directly(self):
        self.auth()
        r = self.client.patch(f"/api/admin/products/{self.milk.id}/", {"stock": 999}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_adjust_stock_cannot_go_negative(self):
        self.auth()
        r = self.client.post(f"/api/admin/products/{self.milk.id}/adjust-stock/",
                             {"delta": -50, "reason": "DAMAGE"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_delete_product_only_deactivates(self):
        self.auth()
        self.client.delete(f"/api/admin/products/{self.milk.id}/")
        self.milk.refresh_from_db()
        self.assertFalse(self.milk.active)

class FirstOwnerBootstrapTests(APITestCase):
    def setUp(self):
        import hashlib
        import os
        from unittest.mock import patch

        self.code = "bootstrap-test-code"
        salt = "test-salt-for-bootstrap"
        digest = hashlib.pbkdf2_hmac("sha256", self.code.encode(), salt.encode(), 310000).hex()
        self.env_patch = patch.dict(os.environ, {"ELSHAMII_DEVELOPER_CODE_HASH": f"{salt}${digest}"})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_first_owner_setup_is_required_initially(self):
        response = self.client.get("/api/auth/bootstrap/status/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["setup_required"])

    def test_first_owner_created_and_setup_locked(self):
        response = self.client.post("/api/auth/bootstrap/", {
            "developer_code": self.code,
            "username": "owner",
            "password": "StrongPass_123!",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data.get("token"))
        self.assertTrue(User.objects.get(username="owner").is_superuser)
        self.assertFalse(self.client.get("/api/auth/bootstrap/status/").data["setup_required"])

        replay = self.client.post("/api/auth/bootstrap/", {
            "developer_code": self.code,
            "username": "another-owner",
            "password": "StrongPass_123!",
        }, format="json")
        self.assertEqual(replay.status_code, 409)
        self.assertFalse(User.objects.filter(username="another-owner").exists())

    def test_owner_can_sign_in_again_after_first_setup(self):
        created = self.client.post("/api/auth/bootstrap/", {
            "developer_code": self.code,
            "username": "owner",
            "password": "StrongPass_123!",
        }, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.data.get("token"))
        self.client.credentials()

        login = self.client.post("/api/auth/login/", {
            "username": "owner",
            "password": "StrongPass_123!",
        }, format="json")
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data.get("token"))
        self.assertFalse(self.client.get("/api/auth/bootstrap/status/").data["setup_required"])

    def test_invalid_developer_code_does_not_create_user(self):
        response = self.client.post("/api/auth/bootstrap/", {
            "developer_code": "wrong-code",
            "username": "owner",
            "password": "StrongPass_123!",
        }, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="owner").exists())
