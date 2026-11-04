from django.urls import path
from rest_framework.routers import SimpleRouter

from . import api_views as v

router = SimpleRouter()
router.register("admin/categories", v.CategoryViewSet, basename="admin-category")
router.register("admin/products", v.ProductViewSet, basename="admin-product")
router.register("admin/orders", v.OrderViewSet, basename="admin-order")

urlpatterns = [
    path("health/", v.health),
    # public
    path("public/categories/", v.PublicCategoryList.as_view()),
    path("public/products/", v.PublicProductList.as_view()),
    path("public/orders/", v.PublicOrderCreate.as_view()),
    path("public/orders/track/<str:token>/", v.PublicOrderTrack.as_view()),
    # staff
    path("auth/bootstrap/status/", v.BootstrapStatusView.as_view()),
    path("auth/bootstrap/", v.BootstrapOwnerView.as_view()),
    path("auth/login/", v.LoginView.as_view()),
    path("auth/logout/", v.LogoutView.as_view()),
    path("admin/dashboard/", v.DashboardView.as_view()),
    path("admin/stock-movements/", v.StockMovementList.as_view()),
] + router.urls
