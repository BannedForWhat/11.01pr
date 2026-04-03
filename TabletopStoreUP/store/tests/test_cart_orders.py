from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from store.models import Product, Genre, Cart, CartItem

User = get_user_model()

class CartOrderFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("u", password="pw")
        self.client.login(username="u", password="pw")
        self.genre = Genre.objects.create(name="Board")
        self.p = Product.objects.create(name="P1", description="", price=100, stock=10, genre=self.genre)

    def test_add_remove_cart_and_list_orders(self):
        # add to cart
        url_add = reverse("store:cart_add", args=[self.p.id])
        resp = self.client.post(url_add, follow=True)
        self.assertEqual(resp.status_code, 200)
        cart = Cart.objects.get(user=self.user)
        self.assertTrue(cart.items.filter(product=self.p).exists())

        # remove item
        item_id = cart.items.first().id
        url_remove = reverse("store:cart_remove", args=[item_id])
        resp = self.client.post(url_remove, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(cart.items.filter(id=item_id).exists())

        # add again and check order list page renders
        self.client.post(url_add, follow=True)
        url_orders = reverse("store:order_list")
        resp = self.client.get(url_orders)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Список заказов", resp.content)
