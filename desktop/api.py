"""Small, timeout-bound client for the Elshamii local Django API."""
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests


class APIError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class StoreAPI:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self.timeout = (3.05, 12)

    def set_token(self, token: str | None) -> None:
        self.session.headers.pop("Authorization", None)
        if token:
            self.session.headers["Authorization"] = f"Token {token}"

    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = self.session.request(method, urljoin(self.base_url, path.lstrip("/")),
                                            timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise APIError("Could not connect to the local store server.") from exc
        try:
            payload = response.json() if response.content else None
        except ValueError:
            payload = None
        if not response.ok:
            detail = "Request failed."
            if isinstance(payload, dict):
                detail = payload.get("detail") or payload.get("error") or detail
                if isinstance(detail, dict):
                    detail = "; ".join(f"{k}: {v}" for k, v in detail.items())
            raise APIError(str(detail), response.status_code, payload)
        return payload

    def health(self) -> dict:
        return self._request("GET", "api/health/")

    def bootstrap_status(self) -> dict:
        return self._request("GET", "api/auth/bootstrap/status/")

    def create_first_owner(self, developer_code: str, username: str, password: str) -> dict:
        result = self._request("POST", "api/auth/bootstrap/", json={
            "developer_code": developer_code, "username": username, "password": password
        })
        if not result.get("token"):
            raise APIError("The server did not return an authentication token.")
        self.set_token(result["token"])
        return result

    def login(self, username: str, password: str) -> dict:
        result = self._request("POST", "api/auth/login/", json={"username": username, "password": password})
        if not result.get("token"):
            raise APIError("The server did not return an authentication token.")
        self.set_token(result["token"])
        return result

    def logout(self) -> None:
        try:
            self._request("POST", "api/auth/logout/")
        finally:
            self.set_token(None)

    def dashboard(self) -> dict:
        return self._request("GET", "api/admin/dashboard/")

    def orders(self, status: str | None = None, query: str = "") -> list[dict]:
        params = {"page_size": 100}
        if status:
            params["status"] = status
        if query.strip():
            params["q"] = query.strip()
        result = self._request("GET", "api/admin/orders/", params=params)
        if isinstance(result, list):
            return result
        return result.get("results", []) if isinstance(result, dict) else []

    def change_order_status(self, order_id: int, status: str, reason: str = "") -> dict:
        return self._request("POST", f"api/admin/orders/{order_id}/status/",
                             json={"status": status, "reason": reason})

    def confirm_payment(self, order_id: int) -> dict:
        return self._request("POST", f"api/admin/orders/{order_id}/confirm-payment/", json={})
    def products(self, query: str = "", category: int | None = None, low_stock: bool = False) -> list[dict]:
        params = {"page_size": 200}
        if query.strip():
            params["q"] = query.strip()
        if category is not None:
            params["category"] = category
        if low_stock:
            params["low_stock"] = "1"
        result = self._request("GET", "api/admin/products/", params=params)
        return result if isinstance(result, list) else result.get("results", [])

    def categories(self) -> list[dict]:
        result = self._request("GET", "api/admin/categories/")
        return result if isinstance(result, list) else result.get("results", [])

    def create_category(self, name_ar: str, name_en: str, sort_order: int = 0) -> dict:
        return self._request("POST", "api/admin/categories/", json={
            "name_ar": name_ar, "name_en": name_en, "sort_order": sort_order, "active": True
        })

    def create_product(self, payload: dict) -> dict:
        return self._request("POST", "api/admin/products/", json=payload)

    def update_product(self, product_id: int, payload: dict) -> dict:
        return self._request("PATCH", f"api/admin/products/{product_id}/", json=payload)

    def deactivate_product(self, product_id: int) -> dict:
        return self._request("DELETE", f"api/admin/products/{product_id}/")

    def adjust_stock(self, product_id: int, delta: int, reason: str, note: str = "") -> dict:
        return self._request("POST", f"api/admin/products/{product_id}/adjust-stock/",
                             json={"delta": delta, "reason": reason, "note": note})

    def stock_movements(self, product_id: int | None = None) -> list[dict]:
        params = {"product": product_id} if product_id is not None else {}
        result = self._request("GET", "api/admin/stock-movements/", params=params)
        return result if isinstance(result, list) else result.get("results", [])

