import os
from pathlib import Path
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command

User = get_user_model()

class BackupDownloadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", password="pw", is_staff=True)
        self.client.login(username="admin", password="pw")

    @override_settings(MEDIA_ROOT="test_media")
    def test_management_backup_and_download(self):
        # сгенерировать бэкап management-командой backup
        call_command("backup")

        # найти созданный файл JSON
        backups_dir = Path(".") / "backups"
        files = sorted(backups_dir.glob("backup_*.json"))
        self.assertTrue(files, "backup_*.json не создан")
        fname = files[-1].name

        # скачать через вьюху
        url = reverse("store:download_backup", args=[fname])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application", resp["Content-Type"])
