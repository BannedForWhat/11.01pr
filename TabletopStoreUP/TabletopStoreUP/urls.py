from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from store.api import (
    UserRoleViewSet, OrderStatusViewSet, PaymentStatusViewSet,
    DeliveryMethodViewSet, DeliveryStatusViewSet, GenreViewSet,
    PlayerRangeViewSet, UserViewSet, ProductViewSet, OrderViewSet,
    OrderItemViewSet, PaymentViewSet, DeliveryViewSet, UserProfileViewSet,
    MeUserSettingsViewSet, ReviewViewSet, PaymentMethodViewSet, RegisterView,
)
from store.api_views import MeUserSettingsViewSet
from store import admin_reports
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

router = DefaultRouter()

router = DefaultRouter()
router.register(r'user-roles', UserRoleViewSet)
router.register(r'order-statuses', OrderStatusViewSet)
router.register(r'payment-statuses', PaymentStatusViewSet)
router.register(r'delivery-methods', DeliveryMethodViewSet)
router.register(r'delivery-statuses', DeliveryStatusViewSet)
router.register(r'genres', GenreViewSet)
router.register(r'player-ranges', PlayerRangeViewSet)
router.register(r'users', UserViewSet, basename='users')
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'order-items', OrderItemViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'deliveries', DeliveryViewSet)
router.register(r'profiles', UserProfileViewSet, basename='profiles')
router.register(r'api/user/settings', MeUserSettingsViewSet, basename='me-settings')
router.register(r'reviews', ReviewViewSet)
router.register(r'payment-methods', PaymentMethodViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('admin/', admin.site.urls),
    path('admin/analytics/', admin_reports.analytics_dashboard, name='admin_analytics'),
    path('admin/analytics/export/', admin_reports.export_analytics_csv, name='export_analytics_csv'),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/auth/register/', RegisterView.as_view(), name='auth_register'),
    path('', include('store.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)