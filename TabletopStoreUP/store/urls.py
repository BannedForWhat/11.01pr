from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from . import admin_reports

app_name = 'store'

urlpatterns = [
    path('', views.ProductListView.as_view(), name='product_list'),

    path('product/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('product/<int:product_id>/review/', views.add_review, name='add_review'),

    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:item_id>/', views.cart_remove, name='cart_remove'),
    path('cart/add-gate/<int:product_id>/', views.cart_add_gate, name='cart_add_gate'),

    path('order/create/', views.order_create, name='create_order'),
    path('order/success/<int:order_id>/', views.order_success_view, name='order_success'),

    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='store/password_reset_form.html',
             email_template_name='store/password_reset_email.html',
             success_url=reverse_lazy('store:password_reset_done')
         ), 
         name='password_reset'),

    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='store/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='store/password_reset_confirm.html',
             success_url=reverse_lazy('store:password_reset_complete')
         ),
         name='password_reset_confirm'),

    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='store/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('api/user/toggle-theme/', views.toggle_theme, name='toggle_theme'),
    path('payments/mock/<int:payment_id>/', views.payment_mock, name='payment_mock'),
    path('payments/mock/<int:payment_id>/callback/', views.payment_mock_callback, name='payment_mock_callback'),
    path('orders/success/<int:order_id>/', views.order_success_view, name='order_success'),

    path('settings/page-size/', views.update_page_size, name='update_page_size'),
    path('catalog/filters/save/', views.save_catalog_filters, name='save_catalog_filters'),
    path('catalog/filters/apply/', views.apply_catalog_filters, name='apply_catalog_filters'),
    path('settings/', views.user_settings_view, name='user_settings'),

    path('catalog/export.csv', views.export_catalog_csv, name='catalog_export_csv'),
    path('catalog/export.json', views.export_catalog_json, name='catalog_export_json'),
    path('catalog/import/', views.import_catalog_view, name='catalog_import'),
    
    path('admin/backups/<str:filename>/', views.download_backup, name='download_backup'),
]
