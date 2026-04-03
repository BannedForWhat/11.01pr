from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.db import transaction

from .models import (
    UserRole, UserProfile, UserSettings,
    Genre, PlayerRange, Product, Review,
    OrderStatus, Order, OrderItem,
    PaymentMethod, PaymentStatus, Payment,
    DeliveryMethod, DeliveryStatus, Delivery,
)

User = get_user_model()


class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = "__all__"


class UserProfileSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(read_only=True)
    role = UserRoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        source="role", queryset=UserRole.objects.all(), write_only=True, required=False
    )

    class Meta:
        model = UserProfile
        fields = ["id", "user", "full_name", "phone", "role", "role_id"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    full_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    role = serializers.SlugRelatedField(
        slug_field="name", queryset=UserRole.objects.all(), required=False
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "full_name", "phone", "role"]

    @transaction.atomic
    def create(self, validated_data):
        full_name = validated_data.pop("full_name", "") or ""
        phone = validated_data.pop("phone", "") or ""
        role = validated_data.pop("role", None)

        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)

        if not role:
            role, _ = UserRole.objects.get_or_create(name="client")

        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={
            "full_name": full_name or user.username,
            "phone": phone or None,
            "role": role
        })
        updated = False
        if full_name and profile.full_name != full_name:
            profile.full_name = full_name
            updated = True
        if phone and profile.phone != phone:
            profile.phone = phone
            updated = True
        if profile.role_id != role.id:
            profile.role = role
            updated = True
        if updated:
            profile.save()

        return user



class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = "__all__"


class PlayerRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerRange
        fields = "__all__"

    def validate(self, data):
        if data["min_players"] > data["max_players"]:
            raise serializers.ValidationError(
                "Минимальное количество игроков не может быть больше максимального."
            )
        return data


class ProductSerializer(serializers.ModelSerializer):
    genre = GenreSerializer(read_only=True)
    player_ranges = PlayerRangeSerializer(many=True, read_only=True)
    avg_rating = serializers.SerializerMethodField(read_only=True)
    image_url = serializers.SerializerMethodField(read_only=True)

    genre_id = serializers.PrimaryKeyRelatedField(
        source="genre", queryset=Genre.objects.all(), write_only=True
    )
    player_range_ids = serializers.PrimaryKeyRelatedField(
        many=True, source="player_ranges", queryset=PlayerRange.objects.all(), write_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id", "name", "description", "price", "stock",
            "genre", "genre_id",
            "player_ranges", "player_range_ids",
            "image", "image_url",
            "avg_rating",
        ]
        extra_kwargs = {
            "image": {"write_only": True, "required": False, "allow_null": True},
        }

    def get_avg_rating(self, obj):
        return round(obj.average_rating() or 0, 2)

    def get_image_url(self, obj):
        try:
            return obj.image.url if obj.image else None
        except Exception:
            return None

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть больше 0.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Количество товара не может быть отрицательным.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        m2m_ranges = validated_data.pop("player_ranges", [])
        product = Product.objects.create(**validated_data)
        if m2m_ranges:
            product.player_ranges.set(m2m_ranges)
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        m2m_ranges = validated_data.pop("player_ranges", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if m2m_ranges is not None:
            instance.player_ranges.set(m2m_ranges)
        return instance


class ReviewSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = Review
        fields = ["id", "product", "user", "rating", "comment", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def validate_rating(self, v):
        if not (1 <= v <= 5):
            raise serializers.ValidationError("Рейтинг должен быть от 1 до 5.")
        return v


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    line_total = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "order", "product", "product_name", "quantity", "price", "line_total"]
        read_only_fields = ["id", "order", "product_name", "line_total"]

    def get_line_total(self, obj):
        return float(obj.price) * obj.quantity

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Количество товара должно быть больше 0.")
        return value

    def validate(self, data):
        product = data.get("product")
        quantity = data.get("quantity")
        if product and quantity and product.stock < quantity:
            raise serializers.ValidationError(f"Недостаточно товара '{product.name}' на складе.")
        return data


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    status = serializers.PrimaryKeyRelatedField(queryset=OrderStatus.objects.all())

    class Meta:
        model = Order
        fields = ["id", "user", "order_date", "status", "total", "items"]
        read_only_fields = ["id", "order_date", "total"]

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order = Order.objects.create(**validated_data)

        total = 0
        for it in items_data:
            product = it["product"]
            qty = it["quantity"]

            if product.stock < qty:
                raise serializers.ValidationError(
                    f"Недостаточно товара {product.name} на складе."
                )

            price = it.get("price") or product.price

            product.stock -= qty
            product.save(update_fields=["stock"])

            OrderItem.objects.create(
                order=order, product=product, quantity=qty, price=price
            )
            total += float(price) * qty

        order.total = total
        order.save(update_fields=["total"])
        return order


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"

    def validate(self, data):
        if data["amount"] <= 0:
            raise serializers.ValidationError("Сумма платежа должна быть больше 0.")
        order = data.get("order")
        if order and float(data["amount"]) != float(order.total):
            raise serializers.ValidationError("Сумма платежа должна совпадать с суммой заказа.")
        return data


class DeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        fields = "__all__"


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = ["theme", "date_format", "number_format", "page_size", "saved_filters"]

    def validate_theme(self, v):
        if v not in dict(UserSettings.THEME_CHOICES):
            raise serializers.ValidationError("Недопустимая тема.")
        return v

    def validate_page_size(self, v):
        if v <= 0 or v > 200:
            raise serializers.ValidationError("Размер страницы должен быть в диапазоне 1..200.")
        return v
    

class OrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatus
        fields = "__all__"


class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentStatus
        fields = "__all__"


class DeliveryMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryMethod
        fields = "__all__"


class DeliveryStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryStatus
        fields = "__all__"


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    full_name = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    role_id = serializers.PrimaryKeyRelatedField(
        source="profile.role", queryset=UserRole.objects.all(), required=False, write_only=True
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "profile",
                  "full_name", "phone", "role_id"]
        read_only_fields = ["id", "username", "profile"]

    def update(self, instance, validated_data):
        profile_data = {
            "full_name": validated_data.pop("full_name", None),
            "phone": validated_data.pop("phone", None),
        }
        _ = validated_data.pop("profile", None)

        password = validated_data.pop("password", None)

        for k, v in validated_data.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()

        profile, _created = UserProfile.objects.get_or_create(
            user=instance,
            defaults={"role": UserRole.objects.get_or_create(name="client")[0]}
        )

        role = self.initial_data.get("role_id", None)
        if role is not None:
            role_obj = None
            try:
                role_obj = self.fields["role_id"].to_internal_value(role)
            except Exception:
                pass
            if role_obj:
                profile.role = role_obj

        if profile_data["full_name"] is not None:
            profile.full_name = profile_data["full_name"] or profile.full_name
        if profile_data["phone"] is not None:
            profile.phone = profile_data["phone"] or profile.phone
        profile.save()

        return instance