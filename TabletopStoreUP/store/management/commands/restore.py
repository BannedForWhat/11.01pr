import os
import re
import sys
import glob
import tarfile
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

BACKUP_DIR = Path(settings.BASE_DIR) / "backups"
DUMP_PATTERN = re.compile(r"backup_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.json$")
MEDIA_PATTERN = re.compile(r"media_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.tar\.gz$")

class Command(BaseCommand):
    help = "Восстанавливает базу данных (и, опционально, медиа) из резервной копии в backups/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            dest="file",
            help="Путь к конкретному JSON дампу (например, backups/backup_2025-10-25_12-34-56.json)",
        )
        parser.add_argument(
            "--latest",
            action="store_true",
            help="Восстановить из самого свежего дампа (по умолчанию так и делается, если --file не указан)",
        )
        parser.add_argument(
            "--media",
            action="store_true",
            help="Также восстановить архив медиа, если найден (media_*.tar.gz).",
        )
        parser.add_argument(
            "--skip-flush",
            action="store_true",
            help="Не выполнять очистку БД (flush). Используйте осторожно.",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Не спрашивать подтверждение (удобно для CI/скриптов).",
        )

    def handle(self, *args, **opts):
        dump_path = self._resolve_dump_path(opts.get("file"), opts.get("latest"))
        if not dump_path.exists():
            raise CommandError(f"Файл дампа не найден: {dump_path}")

        if not opts.get("noinput"):
            self.stdout.write(self.style.WARNING(
                f"Вы собираетесь восстановить БД из:\n  {dump_path}\n"
                f"Каталог бэкапов: {BACKUP_DIR}\n"
                f"{'Также будет восстановлен архив медиа.' if opts.get('media') else ''}"
            ))
            confirm = input("Продолжить? (yes/no): ").strip().lower()
            if confirm not in {"y", "yes"}:
                self.stdout.write("Операция отменена.")
                return

        # 1) Очистка БД
        if not opts.get("skip_flush"):
            self.stdout.write("→ Очищаю текущую БД (flush)...")
            call_command("flush", verbosity=0, interactive=False)

        # 2) Восстановление данных
        self.stdout.write(f"→ Загружаю дамп: {dump_path.name}")
        call_command("loaddata", str(dump_path), verbosity=1)

        # 3) (опц.) Восстановление медиа
        if opts.get("media"):
            media_archive = self._find_matching_media(dump_path)
            if media_archive and media_archive.exists():
                self._restore_media(media_archive)
            else:
                self.stdout.write(self.style.WARNING(
                    "Архив медиа не найден для этого дампа. Пропускаю восстановление медиа."
                ))

        self.stdout.write(self.style.SUCCESS("✅ Восстановление завершено."))

    # --- helpers ---

    def _resolve_dump_path(self, file_opt: str, latest: bool) -> Path:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        if file_opt:
            p = Path(file_opt)
            if not p.is_absolute():
                p = BACKUP_DIR / p
            return p

        dumps = sorted(
            (p for p in BACKUP_DIR.glob("backup_*.json") if DUMP_PATTERN.search(p.name)),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not dumps:
            raise CommandError(f"В каталоге {BACKUP_DIR} не найдено файлов backup_*.json")
        return dumps[0]

    def _find_matching_media(self, dump_path: Path) -> Path | None:
        ts = dump_path.stem.replace("backup_", "")
        exact = BACKUP_DIR / f"media_{ts}.tar.gz"
        if exact.exists():
            return exact
        medias = sorted(
            (p for p in BACKUP_DIR.glob("media_*.tar.gz") if MEDIA_PATTERN.search(p.name)),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return medias[0] if medias else None

    def _restore_media(self, archive_path: Path):
        media_root = Path(getattr(settings, "MEDIA_ROOT", "media"))
        media_root.mkdir(parents=True, exist_ok=True)
        self.stdout.write(f"→ Распаковываю медиа в: {media_root} из {archive_path.name}")
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                member_path = media_root / member.name
                if not str(member_path.resolve()).startswith(str(media_root.resolve())):
                    raise CommandError("Небезопасный путь внутри архива медиа.")
            tar.extractall(path=media_root)
