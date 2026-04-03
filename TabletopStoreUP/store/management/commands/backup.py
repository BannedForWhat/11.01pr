import os
from datetime import datetime
from django.core.management import call_command
from django.conf import settings
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Создаёт резервную копию базы данных и медиа."

    def handle(self, *args, **options):
        # Каталог для бэкапов
        backup_dir = os.path.join(settings.BASE_DIR, "backups")
        os.makedirs(backup_dir, exist_ok=True)

        # Имя файла по дате
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        dump_path = os.path.join(backup_dir, f"backup_{timestamp}.json")

        # Создаём дамп базы
        self.stdout.write(f"→ Создаю бэкап базы данных: {dump_path}")
        with open(dump_path, "w", encoding="utf-8") as f:
            call_command(
                "dumpdata",
                "--natural-primary", "--natural-foreign", "--indent", "2",
                "--exclude", "contenttypes",
                "--exclude", "admin.logentry",
                "--exclude", "sessions",
                stdout=f
            )

        # (опционально) — архив медиа
        media_dir = getattr(settings, "MEDIA_ROOT", None)
        if media_dir and os.path.exists(media_dir):
            archive_name = os.path.join(backup_dir, f"media_{timestamp}")
            import tarfile
            with tarfile.open(f"{archive_name}.tar.gz", "w:gz") as tar:
                tar.add(media_dir, arcname=".")
            self.stdout.write(f"→ Архив медиа сохранён: {archive_name}.tar.gz")

        self.stdout.write(self.style.SUCCESS("✅ Бэкап успешно создан."))
