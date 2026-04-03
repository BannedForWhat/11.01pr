from django.contrib import admin, messages
from django.db.models import Count, F
from django.db import transaction
from django.http import HttpResponse
from django.urls import re_path
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from decimal import Decimal

from . import admin_reports
from .models import (
    UserRole, UserProfile, UserSettings,
    Genre, PlayerRange, Product, Review,
    OrderStatus, Order, OrderItem,
    PaymentMethod, PaymentStatus, Payment,
    DeliveryMethod, DeliveryStatus, Delivery
)

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)

@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "theme", "date_format", "number_format", "page_size", "updated_at")
    list_filter = ("theme",)
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user",)
    readonly_fields = ("updated_at",)

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_editable = ("is_active",)
    search_fields = ("code", "name")

class StockLevelFilter(admin.SimpleListFilter):
    title = "Остаток"
    parameter_name = "stock_level"

    def lookups(self, request, model_admin):
        return [
            ("0", "Нет в наличии"),
            ("lt5", "< 5 шт"),
            ("gte5", "≥ 5 шт"),
        ]

    def queryset(self, request, queryset):
        v = self.value()
        if v == "0":
            return queryset.filter(stock__lte=0)
        if v == "lt5":
            return queryset.filter(stock__gt=0, stock__lt=5)
        if v == "gte5":
            return queryset.filter(stock__gte=5)
        return queryset

class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ("user", "rating", "comment", "created_at")
    can_delete = True
    show_change_link = True

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("thumb", "name", "genre", "price", "stock", "reviews_count")
    list_select_related = ("genre",)
    list_filter = ("genre", StockLevelFilter)
    search_fields = ("name", "description")
    list_editable = ("price", "stock")
    autocomplete_fields = ("genre", "player_ranges")
    filter_horizontal = ("player_ranges",)
    inlines = [ReviewInline]
    readonly_fields = ("image_preview",)

    fieldsets = (
        (None, {"fields": ("name", "description", "genre", "player_ranges")}),
        ("Цена/склад", {"fields": ("price", "stock")}),
        ("Изображение", {"fields": ("image", "image_preview")}),
    )

    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:38px;width:38px;object-fit:cover;border-radius:6px" />', obj.image.url)
        return "—"
    thumb.short_description = ""

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width:260px;border-radius:8px" />', obj.image.url)
        return "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_reviews_count = Count("reviews", distinct=True))

    def reviews_count(self, obj):
        return getattr(obj, "_reviews_count", 0)
    reviews_count.short_description = "Отзывов"
    reviews_count.admin_order_field = "_reviews_count"

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)

@admin.register(PlayerRange)
class PlayerRangeAdmin(admin.ModelAdmin):
    list_display = ("id", "min_players", "max_players")
    list_editable = ("min_players", "max_players")
    search_fields = ("id", "min_players", "max_players")

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "full_name", "phone")
    search_fields = ("user__username", "full_name", "phone", "user__email")
    list_filter = ("role",)
    autocomplete_fields = ("user", "role")

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("product__name", "user__username", "comment")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("product", "user")

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "price", "quantity", "line_total")
    can_delete = False
    autocomplete_fields = ("product",)

    def line_total(self, obj):
        price = obj.price if obj.price is not None else Decimal("0")
        qty = obj.quantity if obj.quantity is not None else 0
        return f"{(price * qty):.2f} ₽"
    line_total.short_description = "Сумма"

class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0
    readonly_fields = ("amount", "status", "method", "payment_date")
    can_delete = False
    autocomplete_fields = ("status", "method")

class DeliveryInline(admin.StackedInline):
    model = Delivery
    extra = 0
    readonly_fields = ("address", "method", "status")
    can_delete = False
    autocomplete_fields = ("method", "status")

@admin.action(description="Отметить как оплаченные")
def mark_paid(modeladmin, request, queryset):
    paid, _ = OrderStatus.objects.get_or_create(name="Paid")
    p_paid, _ = PaymentStatus.objects.get_or_create(name="Paid")
    updated = 0
    with transaction.atomic():
        for order in queryset.select_related():
            Payment.objects.filter(order=order).update(status=p_paid)
            order.status = paid
            order.save(update_fields=["status"])
            updated += 1
    messages.success(request, f"Обновлено заказов: {updated}")

@admin.action(description="Отметить как отгруженные")
def mark_shipped(modeladmin, request, queryset):
    shipped, _ = OrderStatus.objects.get_or_create(name="Shipped")
    d_shipped, _ = DeliveryStatus.objects.get_or_create(name="Shipped")
    updated = 0
    with transaction.atomic():
        for order in queryset:
            Delivery.objects.filter(order=order).update(status=d_shipped)
            order.status = shipped
            order.save(update_fields=["status"])
            updated += 1
    messages.success(request, f"Отгружено заказов: {updated}")

@admin.action(description="Отменить (вернуть на склад)")
def cancel_orders(modeladmin, request, queryset):
    cancelled, _ = OrderStatus.objects.get_or_create(name="Cancelled")
    p_failed, _ = PaymentStatus.objects.get_or_create(name="Failed")
    restored = 0
    with transaction.atomic():
        for order in queryset.prefetch_related("items__product"):
            for it in order.items.all():
                it.product.stock = F("stock") + it.quantity
                it.product.save(update_fields=["stock"])
            Payment.objects.filter(order=order).update(status=p_failed)
            order.status = cancelled
            order.save(update_fields=["status"])
            restored += 1
    messages.warning(request, f"Отменено заказов: {restored}, остатки возвращены.")

@admin.action(description="Экспортировать в CSV")
def export_orders_csv(modeladmin, request, queryset):
    import csv
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="orders.csv"'
    w = csv.writer(resp)
    w.writerow(["id","date","user","status","items","total"])
    for o in queryset.prefetch_related("items__product","user","status"):
        items_str = "; ".join(f"{it.product.name} × {it.quantity} @ {it.price}" for it in o.items.all())
        w.writerow([o.id, o.order_date.strftime("%Y-%m-%d %H:%M"), o.user.username, o.status.name, items_str, f"{o.total:.2f}"])
    return resp

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "order_date", "user", "status", "items_count", "total_fmt")
    list_filter = ("status", "order_date")
    date_hierarchy = "order_date"
    search_fields = ("id", "user__username", "user__email")
    autocomplete_fields = ("user", "status")
    inlines = [OrderItemInline, PaymentInline, DeliveryInline]
    actions = [mark_paid, mark_shipped, cancel_orders, export_orders_csv]
    list_select_related = ("user", "status")
    readonly_fields = ()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_items=Count("items"))

    def items_count(self, obj):
        return getattr(obj, "_items", 0)
    items_count.short_description = "Позиций"
    items_count.admin_order_field = "_items"

    def total_fmt(self, obj):
        return f"{obj.total:.2f} ₽"
    total_fmt.short_description = "Сумма"

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "price", "line_total")
    list_select_related = ("order", "product")
    search_fields = ("order__id", "product__name")
    autocomplete_fields = ("order", "product")

    def line_total(self, obj):
        from decimal import Decimal
        price = obj.price if obj.price is not None else Decimal("0")
        qty = obj.quantity if obj.quantity is not None else 0
        return f"{(price * qty):.2f} ₽"
    line_total.short_description = "Сумма"

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "amount", "status", "method", "payment_date")
    list_filter  = ("status", "method", "payment_date")
    date_hierarchy = "payment_date"
    search_fields = ("order__id",)
    autocomplete_fields = ("order", "status", "method")

@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("order", "address", "method", "status")
    list_filter = ("status", "method")
    search_fields = ("order__id", "address")
    autocomplete_fields = ("order", "method", "status")

@admin.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(PaymentStatus)
class PaymentStatusAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(DeliveryMethod)
class DeliveryMethodAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(DeliveryStatus)
class DeliveryStatusAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

def get_custom_admin_urls(original_get_urls):
    def custom_urls():
        urls = original_get_urls()
        my_urls = [
            re_path(r"^analytics/$", admin_reports.analytics_dashboard, name="admin_analytics"),
            re_path(r"^analytics/export/$", admin_reports.export_analytics_csv, name="export_analytics_csv"),
        ]
        return my_urls + urls
    return custom_urls

admin.site.get_urls = get_custom_admin_urls(admin.site.get_urls)

admin.site.index_title = format_html(
    'Панель управления магазином | <a href="/admin/analytics/" style="color:#6E56CF;text-decoration:none;">📊 Аналитика</a>'
)
admin.site.site_header = "Админ-панель магазина игр"
admin.site.site_title = "Магазин игр — админка"