from io import BytesIO
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from store.models import Genre, PlayerRange, Product

User = get_user_model()

class CatalogImportExportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("staff", password="pw", is_staff=True)
        self.client.login(username="staff", password="pw")

    def test_export_csv_json_ok(self):
        g = Genre.objects.create(name="Board Games")
        p = Product.objects.create(name="Test", description="", price=10, stock=5, genre=g)
        r = PlayerRange.objects.create(min_players=2, max_players=4)
        p.player_ranges.add(r)

        # CSV
        url_csv = reverse("store:catalog_export_csv")
        resp = self.client.get(url_csv)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        body = resp.content.decode("utf-8")
        self.assertIn("Test", body)
        self.assertIn("2-4", body)

        # JSON
        url_json = reverse("store:catalog_export_json")
        resp = self.client.get(url_json)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp["Content-Type"])
        self.assertIn('"name": "Test"', resp.content.decode("utf-8"))

    def test_import_csv_creates_and_updates(self):
        csv = (
            "id,name,description,price,stock,genre,player_ranges\n"
            ",Alpha,,19.99,7,Card,2-4\n"
            ",Beta,,9.50,2,Board,1-2;3-5\n"
        ).encode("utf-8")
        url = reverse("store:catalog_import")
        resp = self.client.post(url, data={"file": BytesIO(csv)}, format="multipart")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Product.objects.filter(name__iexact="Alpha").exists())
        self.assertTrue(Product.objects.filter(name__iexact="Beta").exists())
        self.assertTrue(Genre.objects.filter(name="Card").exists())
        self.assertTrue(Genre.objects.filter(name="Board").exists())

        # update Alpha stock
        csv2 = "id,name,description,price,stock,genre,player_ranges\n,Alpha,,19.99,10,Card,2-4\n".encode()
        resp2 = self.client.post(url, data={"file": BytesIO(csv2)}, format="multipart")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(Product.objects.get(name="Alpha").stock, 10)
