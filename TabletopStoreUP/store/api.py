from rest_framework import viewsets, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Avg
from .models import (
    UserRole, UserProfile, UserSettings,
    Genre, PlayerRange, Product, Review,
    OrderStatus, Order, OrderItem,
    PaymentMethod, PaymentStatus, Payment,
    DeliveryMethod, DeliveryStatus, Delivery,
)
from .serializers import (
    UserRoleSerializer, UserProfileSerializer, UserSettingsSerializer,
    GenreSerializer, PlayerRangeSerializer,
    ProductSerializer, ReviewSerializer,
    OrderStatusSerializer, OrderSerializer, OrderItemSerializer,
    PaymentMethodSerializer, PaymentStatusSerializer, PaymentSerializer,
    DeliveryMethodSerializer, DeliveryStatusSerializer, DeliverySerializer,
    RegisterSerializer, UserSerializer,
)

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class MeUserSettingsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    def list(self, request):
        return Response(UserSettingsSerializer(request.user.settings).data)
    def update(self, request):
        s = request.user.settings
        ser = UserSettingsSerializer(s, data=request.data, partial=True)
        ser.is_valid(raise_exception=True); ser.save()
        return Response(ser.data)

class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = [permissions.AllowAny]

class PlayerRangeViewSet(viewsets.ModelViewSet):
    queryset = PlayerRange.objects.all()
    serializer_class = PlayerRangeSerializer
    permission_classes = [permissions.AllowAny]

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.prefetch_related("reviews", "player_ranges")
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["get"])
    def top(self, request):
        top = Product.objects.annotate(avg=Avg("reviews__rating")).order_by("-avg")[:5]
        return Response([{"id": p.id, "name": p.name, "avg": round(p.average_rating() or 0, 2)} for p in top])

    @action(detail=False, methods=["get"])
    def stats(self, request):
        return Response({
            "total_products": Product.objects.count(),
            "avg_rating": round(Review.objects.aggregate(a=Avg("rating"))["a"] or 0, 2),
            "total_reviews": Review.objects.count(),
            "total_orders": Order.objects.count(),
        })

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related("product", "user")
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class OrderStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrderStatus.objects.all()
    serializer_class = OrderStatusSerializer
    permission_classes = [permissions.AllowAny]

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related("user", "status")
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        qs = super().get_queryset()
        return qs if self.request.user.is_staff else qs.filter(user=self.request.user)
    @action(detail=True, methods=["post"])
    def mark_paid(self, request, pk=None):
        order = self.get_object()
        ps_paid, _ = PaymentStatus.objects.get_or_create(name="Paid")
        st_paid, _ = OrderStatus.objects.get_or_create(name="Paid")
        order.payment.status = ps_paid; order.payment.save(update_fields=["status"])
        order.status = st_paid; order.save(update_fields=["status"])
        return Response({"detail": f"Заказ #{order.id} отмечен как оплаченный."})

class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.select_related("order", "product")
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAdminUser]

class PaymentMethodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PaymentMethod.objects.filter(is_active=True)
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.AllowAny]

class PaymentStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PaymentStatus.objects.all()
    serializer_class = PaymentStatusSerializer
    permission_classes = [permissions.AllowAny]

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("order", "status", "method")
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAdminUser]

class DeliveryMethodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeliveryMethod.objects.all()
    serializer_class = DeliveryMethodSerializer
    permission_classes = [permissions.AllowAny]

class DeliveryStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeliveryStatus.objects.all()
    serializer_class = DeliveryStatusSerializer
    permission_classes = [permissions.AllowAny]

class DeliveryViewSet(viewsets.ModelViewSet):
    queryset = Delivery.objects.select_related("order", "method", "status")
    serializer_class = DeliverySerializer
    permission_classes = [permissions.IsAdminUser]

class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAdminUser]

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.select_related("user", "role")
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAdminUser]