from locust import HttpUser, task, between
import random, re

class Shopper(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Логинимся 1 раз перед всеми задачами"""
        login_page = self.client.get("/login/")
        csrf = re.search(r"name='csrfmiddlewaretoken' value='(.+?)'", login_page.text)
        if csrf:
            token = csrf.group(1)
            self.client.post(
                "/login/",
                data={
                    "csrfmiddlewaretoken": token,
                    "username": "client",
                    "password": "client123",
                },
                headers={"Referer": "/login/"},
            )

    @task(3)
    def browse_products(self):
        self.client.get("/")

    @task(2)
    def product_detail(self):
        pid = random.randint(1, 4)
        self.client.get(f"/product/{pid}/")

    @task
    def add_to_cart(self):
        pid = random.randint(1, 4)
        self.client.post(f"/cart/add/{pid}/")

    @task
    def open_cart(self):
        self.client.get("/cart/")

    @task
    def orders_list(self):
        self.client.get("/orders/")
