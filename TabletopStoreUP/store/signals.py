from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth.models import User
from .models import UserProfile, UserRole, UserSettings, OrderStatus, PaymentStatus, PaymentMethod, DeliveryMethod, DeliveryStatus, Genre, PlayerRange, Product
from decimal import Decimal


def _yes(val: str) -> bool:
    return str(val).lower() in ("1", "true", "yes", "y", "on")


@receiver(post_migrate)
def seed_reference_and_demo(sender, **kwargs):
    if getattr(sender, "label", None) != "store":
        return

    for name in ["guest", "client", "manager", "admin"]:
        UserRole.objects.get_or_create(name=name)

    for name in ["New", "Paid", "Awaiting Shipment", "Shipped", "Completed", "Cancelled", "Payment Failed"]:
        OrderStatus.objects.get_or_create(name=name)

    for name in ["Pending", "Authorized", "Paid", "Failed", "Refunded"]:
        PaymentStatus.objects.get_or_create(name=name)

    PaymentMethod.objects.get_or_create(code="cod", defaults={"name": "Оплата при получении", "is_active": True})
    PaymentMethod.objects.get_or_create(code="card", defaults={"name": "Банковская карта", "is_active": True})
    PaymentMethod.objects.get_or_create(code="sbp", defaults={"name": "СБП (имитация)", "is_active": True})

    for name in ["Standard", "Express"]:
        DeliveryMethod.objects.get_or_create(name=name)

    for name in ["Pending", "Shipped", "Delivered"]:
        DeliveryStatus.objects.get_or_create(name=name)

    genres = ["Евро", "Кооператив", "Семейная", "Варгейм", "Стратегия"]
    genre_map = {}
    for g in genres:
        obj, _ = Genre.objects.get_or_create(name=g)
        genre_map[g] = obj

    pr_defs = [(1, 2), (2, 4), (3, 4), (3, 6), (1, 5)]
    pr_map = []
    for mn, mx in pr_defs:
        obj, _ = PlayerRange.objects.get_or_create(min_players=mn, max_players=mx)
        pr_map.append(obj)

    if settings.DEBUG and _yes(getattr(settings, "SEED_DEMO", "1")):
        manager_username = "manager"
        client_username = "client"

        manager = User.objects.filter(username=manager_username).first()
        if not manager:
            manager = User.objects.create_user(
                username=manager_username,
                email="manager@example.com",
                password="manager123",
                is_staff=True
            )
        _ensure_profile_with_role(manager, "manager")

        client = User.objects.filter(username=client_username).first()
        if not client:
            client = User.objects.create_user(
                username=client_username,
                email="client@example.com",
                password="client123",
                is_staff=False
            )
        _ensure_profile_with_role(client, "client")

        if Product.objects.count() == 0:
            demo = [
                {
                    "name": "Warhammer 40000",
                    "description": "Миниатюры, варгейм. Базовый набор.",
                    "price": Decimal("5000.00"),
                    "stock": 15,
                    "genre": genre_map["Варгейм"],
                    "players": [(2, 4)],
                },
                {
                    "name": "Catan",
                    "description": "Классическая семейная евро-стратегия.",
                    "price": Decimal("3200.00"),
                    "stock": 28,
                    "genre": genre_map["Евро"],
                    "players": [(3, 4), (3, 6)],
                },
                {
                    "name": "Pandemic",
                    "description": "Кооператив на спасение мира.",
                    "price": Decimal("3400.00"),
                    "stock": 20,
                    "genre": genre_map["Кооператив"],
                    "players": [(2, 4)],
                },
                {
                    "name": "Ticket to Ride",
                    "description": "Семейная игра с поездами.",
                    "price": Decimal("2900.00"),
                    "stock": 30,
                    "genre": genre_map["Семейная"],
                    "players": [(2, 4), (1, 5)],
                },
            ]
            for d in demo:
                p = Product.objects.create(
                    name=d["name"],
                    description=d["description"],
                    price=d["price"],
                    stock=d["stock"],
                    genre=d["genre"],
                )
                for mn, mx in d["players"]:
                    pr = PlayerRange.objects.get(min_players=mn, max_players=mx)
                    p.player_ranges.add(pr)




def _ensure_profile_with_role(user: User, role_name: str):
    role, _ = UserRole.objects.get_or_create(name=role_name)
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={"full_name": user.username, "role": role},
    )
    if not created and profile.role_id != role.id:
        profile.role = role
        profile.save(update_fields=["role"])
    UserSettings.objects.get_or_create(user=user)


@receiver(post_save, sender=User)
def ensure_profile_settings_on_user_change(sender, instance: User, created, **kwargs):
    role_name = "admin" if instance.is_superuser else "client"
    _ensure_profile_with_role(instance, role_name)

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    role_name = "admin" if instance.is_superuser else "client"
    role, _ = UserRole.objects.get_or_create(name=role_name)
    profile, created_profile = UserProfile.objects.get_or_create(
        user=instance,
        defaults={'full_name': instance.username, 'role': role}
    )
    if not created_profile and profile.role != role:
        profile.role = role
        profile.save(update_fields=['role'])

@receiver(post_save, sender=User)
def create_user_settings(sender, instance, created, **kwargs):
    if created:
        UserSettings.objects.get_or_create(user=instance)