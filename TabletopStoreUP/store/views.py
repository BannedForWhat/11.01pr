from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model, REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Avg, Count, Q, Subquery, OuterRef, FloatField, Value
from django.db.models.functions import Coalesce
from django.http import (
    JsonResponse, HttpResponseForbidden, HttpResponseRedirect,
    FileResponse, HttpResponseBadRequest, HttpResponse
)
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.conf import settings
from django.http import QueryDict
from .forms import (
    RegisterForm, LoginForm, ReviewForm,
    OrderCreateForm, UserSettingsForm
)
from .models import (
    UserRole, OrderStatus, PaymentStatus, DeliveryMethod, DeliveryStatus,
    Genre, PlayerRange, Product, Order, OrderItem, Payment, Delivery,
    UserProfile, Cart, CartItem, Review, UserSettings, PaymentMethod
)
import csv, io, json, re

import os

User = get_user_model()


class ProductListView(ListView):
    model = Product
    template_name = 'store/product_list.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        base = (
            Product.objects
            .select_related('genre')
            .prefetch_related('player_ranges')
            .annotate(orderitems_count=Count('orderitem', distinct=True))
        )

        avg_subq = (
            Review.objects
            .filter(product_id=OuterRef('pk'))
            .values('product_id')
            .annotate(a=Avg('rating'))
            .values('a')[:1]
        )

        qs = base.annotate(
            avg_rating=Coalesce(Subquery(avg_subq, output_field=FloatField()), Value(0.0))
        )

        p = self.request.GET

        q = (p.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        if p.get('genre'):
            qs = qs.filter(genre_id=p['genre'])

        if p.get('in_stock') == '1':
            qs = qs.filter(stock__gt=0)

        if p.get('price_min'):
            qs = qs.filter(price__gte=p['price_min'])

        if p.get('price_max'):
            qs = qs.filter(price__lte=p['price_max'])

        if p.get('rating_min'):
            qs = qs.filter(avg_rating__gte=p['rating_min'])

        players = p.getlist('players')
        if players:
            qs = qs.filter(player_ranges__in=players).distinct()

        sort = p.get('sort') or 'new'
        sort_map = {
            'price_asc': 'price',
            'price_desc': '-price',
            'rating_desc': '-avg_rating',
            'rating_asc': 'avg_rating',
            'popular': '-orderitems_count',
            'new': '-id',
        }
        return qs.order_by(sort_map.get(sort, '-id'))

    def get_paginate_by(self, queryset):
        if self.request.user.is_authenticated and hasattr(self.request.user, 'settings'):
            try:
                return int(self.request.user.settings.page_size or self.paginate_by)
            except Exception:
                return self.paginate_by
        return self.paginate_by

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params: QueryDict = self.request.GET.copy()

        def _page_url(page: int) -> str:
            p = params.copy()
            p['page'] = str(page)
            return f"{self.request.path}?{p.urlencode()}"

        page_obj = ctx.get('page_obj')
        ctx['next_page_url'] = _page_url(page_obj.next_page_number()) if page_obj and page_obj.has_next() else ''
        ctx['prev_page_url'] = _page_url(page_obj.previous_page_number()) if page_obj and page_obj.has_previous() else ''

        ctx['genres'] = Genre.objects.all().order_by('name')
        ctx['player_ranges'] = PlayerRange.objects.all().order_by('min_players', 'max_players')

        ctx['current'] = {
            'q': self.request.GET.get('q', ''),
            'genre': self.request.GET.get('genre', ''),
            'in_stock': self.request.GET.get('in_stock', ''),
            'price_min': self.request.GET.get('price_min', ''),
            'price_max': self.request.GET.get('price_max', ''),
            'rating_min': self.request.GET.get('rating_min', ''),
            'players': self.request.GET.getlist('players'),
            'sort': self.request.GET.get('sort', 'new'),
        }

        ctx['has_active_filters'] = any([
            ctx['current']['genre'], ctx['current']['in_stock'],
            ctx['current']['price_min'], ctx['current']['price_max'],
            ctx['current']['rating_min'], ctx['current']['players']
        ])

        ctx['save_filters_url'] = reverse('store:save_catalog_filters')
        ctx['apply_filters_url'] = reverse('store:apply_catalog_filters')
        ctx['page_sizes'] = [8, 12, 16, 24, 32, 48]
        ctx['reset_url'] = self.request.path
        return ctx


class ProductDetailView(DetailView):
    model = Product
    template_name = 'store/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reviews = self.object.reviews.all()
        avg_rating = reviews.aggregate(average=Avg('rating'))['average'] or 0
        context['reviews'] = reviews
        context['avg_rating'] = avg_rating
        return context


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.full_name = form.cleaned_data.get('full_name') or user.username
                profile.phone = form.cleaned_data.get('phone') or ''
                if not profile.role_id:
                    role, _ = UserRole.objects.get_or_create(name='client')
                    profile.role = role
                profile.save()
            login(request, user)
            messages.success(request, "Регистрация успешна!")
            return redirect('store:product_list')
    else:
        form = RegisterForm()
    return render(request, 'store/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "Вы вошли в систему.")
            return redirect('store:product_list')
        else:
            messages.error(request, "Неправильный логин или пароль.")
    else:
        form = LoginForm()
    return render(request, 'store/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('store:product_list')


@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product')
    total = sum(item.product.price * item.quantity for item in items)
    return render(request, 'store/cart_detail.html', {'cart': cart, 'items': items, 'total': total})


@login_required
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if product.stock <= 0:
        messages.error(request, "Товар закончился.")
        return redirect('store:product_detail', pk=product_id)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': 0})
    if item.quantity < product.stock:
        item.quantity += 1
        item.save(update_fields=['quantity'])
        messages.success(request, f'{product.name} добавлен в корзину.')
    else:
        messages.warning(request, f'Достигнуто максимальное количество ({product.stock}).')
    return redirect('store:cart_detail')


@login_required
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    if item.quantity > 1:
        item.quantity -= 1
        item.save(update_fields=['quantity'])
        messages.info(request, f'Количество {item.product.name} уменьшено на 1.')
    else:
        item.delete()
        messages.info(request, f'{item.product.name} удалён из корзины.')
    return redirect('store:cart_detail')


def cart_add_gate(request, product_id):
    """Гостя отправляем на логин и возвращаемся с добавлением qty."""
    try:
        qty = int(request.GET.get('qty', 1))
        qty = max(1, min(999, qty))
    except ValueError:
        return HttpResponseBadRequest("Bad qty")

    if not request.user.is_authenticated:
        next_url = f"{reverse('store:cart_add_gate', args=[product_id])}?qty={qty}"
        login_url = f"{reverse('store:login')}?{REDIRECT_FIELD_NAME}={next_url}"
        return redirect(login_url)

    product = get_object_or_404(Product, pk=product_id, stock__gt=0)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    item, _ = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': 0})

    new_qty = min(product.stock, item.quantity + qty)
    if new_qty == item.quantity:
        messages.warning(request, f"Нельзя добавить больше доступного количества ({product.stock}).")
    else:
        item.quantity = new_qty
        item.save(update_fields=['quantity'])
        messages.success(request, f"Добавлено в корзину: «{product.name}» × {qty}")

    return redirect('store:cart_detail')


@login_required
def order_create(request):
    cart = get_object_or_404(Cart, user=request.user)
    items = cart.items.select_related('product')
    if not items.exists():
        messages.error(request, "Ваша корзина пуста.")
        return redirect('store:product_list')

    total = sum(i.product.price * i.quantity for i in items)

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Проверьте форму.")
            return render(request, 'store/order_create.html', {'cart': cart, 'form': form, 'total': total})

        address = form.cleaned_data['address']
        method: PaymentMethod = form.cleaned_data['payment_method']

        with transaction.atomic():
            status_new, _ = OrderStatus.objects.get_or_create(name="New")
            order = Order.objects.create(user=request.user, status=status_new, total=total)

            for item in items:
                if item.product.stock < item.quantity:
                    messages.error(request, f"Недостаточно товара: {item.product.name}")
                    raise transaction.TransactionManagementError("Out of stock")
                OrderItem.objects.create(
                    order=order, product=item.product, quantity=item.quantity, price=item.product.price
                )
                item.product.stock -= item.quantity
                item.product.save(update_fields=['stock'])

            d_status, _ = DeliveryStatus.objects.get_or_create(name="Pending")
            d_method, _ = DeliveryMethod.objects.get_or_create(name="Standard")
            Delivery.objects.create(order=order, address=address, method=d_method, status=d_status)

            p_status, _ = PaymentStatus.objects.get_or_create(name="Pending")
            payment = Payment.objects.create(order=order, amount=order.total, status=p_status, method=method)

            if method.code == 'cod':
                ps, _ = PaymentStatus.objects.get_or_create(name="Authorized")
                os, _ = OrderStatus.objects.get_or_create(name="Awaiting Shipment")
                payment.status = ps; payment.save(update_fields=['status'])
                order.status = os; order.save(update_fields=['status'])
                items.delete()
                messages.success(request, f'Заказ #{order.id} оформлен. Оплата при получении.')
                return redirect('store:order_success', order.id)

        return redirect('store:payment_mock', payment_id=payment.id)

    form = OrderCreateForm(initial={'address': ''})
    return render(request, 'store/order_create.html', {'cart': cart, 'form': form, 'total': total})


@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/order_success.html', {'order': order})


@login_required
def order_list(request):
    if request.user.is_staff:
        orders = Order.objects.all().select_related('user', 'status')
    else:
        orders = Order.objects.filter(user=request.user).select_related('status')
    return render(request, 'store/order_list.html', {'orders': orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not request.user.is_staff and order.user != request.user:
        messages.error(request, "У вас нет доступа к этому заказу.")
        return redirect('store:order_list')

    items = order.items.select_related('product')
    for it in items:
        it.total_price = it.price * it.quantity

    context = {'order': order, 'items': items, 'delivery': getattr(order, 'delivery', None),
               'payment': getattr(order, 'payment', None)}
    return render(request, 'store/order_detail.html', context)


@login_required
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if Review.objects.filter(product=product, user=request.user).exists():
        messages.error(request, "Вы уже оставили отзыв для этого товара.")
        return redirect('store:product_detail', pk=product.id)

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            messages.success(request, "Ваш отзыв успешно добавлен!")
            return redirect('store:product_detail', pk=product.id)
    else:
        form = ReviewForm()
    return render(request, 'store/add_review.html', {'product': product, 'form': form})



@staff_member_required
def analytics_dashboard(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    orders = Order.objects.all()
    if start_date:
        orders = orders.filter(order_date__date__gte=start_date)
    if end_date:
        orders = orders.filter(order_date__date__lte=end_date)

    total_orders = orders.count()
    total_revenue = orders.aggregate_sum = orders.aggregate(total_sum=Count('id'))
    total_revenue = orders.aggregate_sum if isinstance(total_revenue, (int, float)) else (orders.aggregate_sum or 0)

    total_revenue = orders.aggregate_sum
    total_revenue = orders.aggregate_sum or 0

    total_revenue = orders.aggregate_sum if orders else 0

    from django.db.models import Sum
    total_revenue = orders.aggregate(Sum('total'))['total__sum'] or 0
    avg_order = (total_revenue / total_orders) if total_orders else 0
    unique_users = orders.values('user').distinct().count()

    sales_by_date = (
        orders.extra({'day': "date(order_date)"}).values('day').annotate(total=Sum('total')).order_by('day')
    )
    top_products = (
        OrderItem.objects.filter(order__in=orders)
        .values('product__name').annotate(total_quantity=Sum('quantity'))
        .order_by('-total_quantity')[:5]
    )
    orders_by_user = (
        orders.values('user__username').annotate(count=Count('id')).order_by('-count')[:5]
    )

    context = {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'avg_order': avg_order,
        'unique_users': unique_users,
        'sales_by_date': list(sales_by_date),
        'top_products': list(top_products),
        'orders_by_user': list(orders_by_user),
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'store/analytics.html', context)

@staff_member_required
def download_backup(request, filename):
    path = os.path.join(settings.BASE_DIR, "backups", filename)
    return FileResponse(open(path, "rb"), as_attachment=True)


@login_required
@require_POST
def toggle_theme(request):
    with transaction.atomic():
        us, _ = UserSettings.objects.get_or_create(user=request.user)
        us.theme = 'dark' if us.theme != 'dark' else 'light'
        us.save(update_fields=['theme'])
    return JsonResponse({'status': 'ok', 'theme': us.theme})

@login_required
@require_POST
def update_page_size(request):
    us, _ = UserSettings.objects.get_or_create(user=request.user)
    try:
        ps = max(1, min(100, int(request.POST.get('page_size', 12))))
    except ValueError:
        ps = 12
    us.page_size = ps
    us.save(update_fields=['page_size'])
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

@login_required
def save_catalog_filters(request):
    us, _ = UserSettings.objects.get_or_create(user=request.user)
    data = request.GET.copy()
    data.pop('page', None)
    us.saved_filters['catalog'] = data
    us.save(update_fields=['saved_filters'])
    messages.success(request, "Фильтры сохранены.")
    return redirect('store:product_list')

@login_required
def apply_catalog_filters(request):
    us, _ = UserSettings.objects.get_or_create(user=request.user)
    params = us.saved_filters.get('catalog', {})
    if not params:
        messages.info(request, "Сохранённых фильтров нет.")
        return redirect('store:product_list')
    query = urlencode(params, doseq=True)
    return redirect(f"{reverse('store:product_list')}?{query}")


@login_required
def payment_mock(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    if payment.order.user_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden("Not your payment")
    return render(request, 'store/payment_mock.html', {'payment': payment})

@login_required
@require_POST
@transaction.atomic
def payment_mock_callback(request, payment_id):
    outcome = request.POST.get('outcome')
    payment = get_object_or_404(Payment.objects.select_for_update(), pk=payment_id)

    if payment.order.user_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden("Not your payment")

    p_paid, _ = PaymentStatus.objects.get_or_create(name="Paid")
    p_failed, _ = PaymentStatus.objects.get_or_create(name="Failed")
    s_paid, _ = OrderStatus.objects.get_or_create(name="Paid")
    s_failed, _ = OrderStatus.objects.get_or_create(name="Payment Failed")

    if outcome == 'success':
        payment.status = p_paid
        payment.save(update_fields=['status'])
        payment.order.status = s_paid
        payment.order.save(update_fields=['status'])
        CartItem.objects.filter(cart__user=payment.order.user).delete()
        return redirect('store:order_success', payment.order_id)
    else:
        payment.status = p_failed
        payment.save(update_fields=['status'])
        payment.order.status = s_failed
        payment.order.save(update_fields=['status'])
        return render(request, 'store/payment_failed.html', {'order': payment.order, 'payment': payment})
    
@login_required
def user_settings_view(request):
    """Просмотр и изменение пользовательских настроек (тема, формат, размер страниц)."""
    us, _ = UserSettings.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserSettingsForm(request.POST, instance=us)
        if form.is_valid():
            form.save()
            messages.success(request, "Настройки сохранены.")
            return redirect('store:user_settings')
    else:
        form = UserSettingsForm(instance=us)
    return render(request, 'store/user_settings.html', {'form': form})

@staff_member_required
def export_catalog_csv(request):
    """Экспорт каталога (Product + Genre + PlayerRange) в CSV."""
    from .models import Product  # локальный импорт, чтобы избежать циклов
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    headers = ["id", "name", "description", "price", "stock", "genre", "player_ranges"]
    writer.writerow(headers)

    qs = Product.objects.select_related("genre").prefetch_related("player_ranges").order_by("id")
    for p in qs:
        pr = ";".join(f"{r.min_players}-{r.max_players}" for r in p.player_ranges.all())
        writer.writerow([
            p.id,
            p.name,
            p.description,
            str(p.price),
            p.stock,
            p.genre.name if p.genre_id else "",
            pr,
        ])

    resp = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="catalog.csv"'
    return resp


@staff_member_required
def export_catalog_json(request):
    """Экспорт каталога в JSON."""
    from .models import Product
    data = []
    qs = Product.objects.select_related("genre").prefetch_related("player_ranges").order_by("id")
    for p in qs:
        data.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price": float(p.price),
            "stock": p.stock,
            "genre": p.genre.name if p.genre_id else None,
            "player_ranges": [f"{r.min_players}-{r.max_players}" for r in p.player_ranges.all()],
        })
    js = json.dumps(data, ensure_ascii=False, indent=2)
    resp = HttpResponse(js, content_type="application/json; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="catalog.json"'
    return resp


@staff_member_required
def import_catalog_view(request):
    """
    Импорт каталога из CSV/JSON.
    CSV-колонки: id(опц.), name, description, price, stock, genre, player_ranges (например: "2-4;3-6").
    JSON — список объектов с теми же полями. 
    Поиск существующих: сперва по id, затем по name (без регистра).
    Жанры и диапазоны игроков создаются при необходимости.
    """

    if request.method == "POST" and request.FILES.get("file"):
        f = request.FILES["file"]
        ext = (f.name.rsplit(".", 1)[-1] if "." in f.name else "").lower()
        created = updated = 0
        errors = []

        def get_or_create_range(s: str):
            s = (s or "").strip()
            if not s:
                return None
            m = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", s)
            if not m:
                return None
            a, b = int(m.group(1)), int(m.group(2))
            obj, _ = PlayerRange.objects.get_or_create(min_players=a, max_players=b)
            return obj

        try:
            # читаем данные
            if ext in ("csv", "tsv"):
                decoded = f.read().decode("utf-8-sig")
                rows = list(csv.DictReader(io.StringIO(decoded)))
            else:
                rows = json.load(f)

            for idx, row in enumerate(rows, start=1):
                try:
                    # Унификация полей
                    if isinstance(row, dict):
                        name = (row.get("name") or "").strip()
                        desc = row.get("description") or ""
                        price = row.get("price") or 0
                        stock = int(row.get("stock") or 0)
                        genre_name = (row.get("genre") or "").strip()
                        pr_raw = row.get("player_ranges") or ""
                        if isinstance(pr_raw, str):
                            pr_list = [s for s in pr_raw.split(";") if s.strip()]
                        else:
                            pr_list = list(pr_raw)
                        pid = row.get("id")
                    else:
                        # CSV-строка
                        name = (row.get("name") or "").strip()
                        desc = row.get("description") or ""
                        price = row.get("price") or "0"
                        stock = int(row.get("stock") or 0)
                        genre_name = (row.get("genre") or "").strip()
                        pr_list = [s for s in (row.get("player_ranges") or "").split(";") if s.strip()]
                        pid = row.get("id")

                    if not name:
                        errors.append(f"Строка {idx}: отсутствует name")
                        continue

                    genre = None
                    if genre_name:
                        genre, _ = Genre.objects.get_or_create(name=genre_name)

                    # Поиск существующего товара
                    obj = None
                    if pid:
                        try:
                            obj = Product.objects.get(id=int(pid))
                        except Product.DoesNotExist:
                            obj = None
                    if obj is None:
                        obj = Product.objects.filter(name__iexact=name).first()

                    # Создание/обновление
                    if obj is None:
                        obj = Product.objects.create(
                            name=name,
                            description=desc,
                            price=price,
                            stock=stock,
                            genre=genre,
                        )
                        created += 1
                    else:
                        obj.name = name
                        obj.description = desc
                        obj.price = price
                        obj.stock = stock
                        obj.genre = genre
                        obj.save()
                        updated += 1

                    # Диапазоны игроков
                    ranges = [get_or_create_range(s) for s in pr_list]
                    ranges = [r for r in ranges if r is not None]
                    if ranges:
                        obj.player_ranges.set(ranges)
                    else:
                        obj.player_ranges.clear()

                except Exception as e:
                    errors.append(f"Строка {idx}: {e}")

            return render(request, "store/catalog_import_result.html", {
                "created": created, "updated": updated, "errors": errors
            })

        except Exception as e:
            return render(request, "store/catalog_import_result.html", {
                "created": 0, "updated": 0, "errors": [str(e)]
            })

    # GET — форма загрузки
    return render(request, "store/catalog_import.html", {})