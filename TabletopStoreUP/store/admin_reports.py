from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Sum, Count, Avg
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from .models import Order, OrderItem
import csv
import datetime

@staff_member_required
def analytics_dashboard(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        start_date = parse_date(start_date)
    if end_date:
        end_date = parse_date(end_date)
    if not start_date:
        start_date = datetime.date.today() - datetime.timedelta(days=30)
    if not end_date:
        end_date = datetime.date.today()

    orders = Order.objects.filter(order_date__date__range=(start_date, end_date))

    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Sum('total'))['total'] or 0
    avg_check = orders.aggregate(avg=Avg('total'))['avg'] or 0
    unique_customers = orders.values('user').distinct().count()

    daily_revenue = (
        orders.values('order_date__date')
        .annotate(total=Sum('total'))
        .order_by('order_date__date')
    )

    popular_products = (
        OrderItem.objects
        .filter(order__in=orders)
        .values('product__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:10]
    )

    user_activity = (
        orders
        .values('order_date__date')
        .annotate(total_orders=Count('id'))
        .order_by('order_date__date')
    )

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'avg_check': avg_check,
        'unique_customers': unique_customers,
        'daily_revenue': daily_revenue,
        'popular_products': popular_products,
        'user_activity': user_activity,
    }

    return render(request, 'admin/analytics_dashboard.html', context)


@staff_member_required
def export_analytics_csv(request):
    """Экспорт данных аналитики в CSV"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="analytics_report.csv"'
    response.write('\ufeff'.encode('utf8'))
    start_date = parse_date(request.GET.get('start_date'))
    end_date = parse_date(request.GET.get('end_date'))

    if not start_date or not end_date:
        start_date = datetime.date.today() - datetime.timedelta(days=30)
        end_date = datetime.date.today()

    daily_revenue = (
        Order.objects.filter(order_date__date__range=(start_date, end_date))
        .values('order_date__date')
        .annotate(total=Sum('total'))
        .order_by('order_date__date')
    )

    writer = csv.writer(response)
    writer.writerow(['Дата', 'Заказы', 'Выручка (₽)'])
    for day in daily_revenue:
        writer.writerow([day['order_date__date'], day['total']])

    return response
