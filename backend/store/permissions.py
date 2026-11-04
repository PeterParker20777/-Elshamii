from rest_framework.permissions import BasePermission


class IsStoreStaff(BasePermission):
    """Active staff users only (the supermarket's employees and administrators)."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.is_staff)
