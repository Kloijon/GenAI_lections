import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class DirectoryWatcherTool:
    """Инструмент для отслеживания изменений в директории."""

    name = "directory_watcher"
    description = (
        "Отслеживает изменения в указанной директории в реальном времени. "
        "Обнаруживает создание, удаление, изменение и перемещение файлов и папок. "
    )

    def use(self, path: str = ".", duration: Optional[int] = None, details: bool = True) -> str:
        """Запускает отслеживание изменений в директории."""
        try:
            watching_path = Path(path)
            if not watching_path.exists():
                watching_path.mkdir(parents=True, exist_ok=True)
                if details:
                    print(f"> Директория не существовала, создана: '{path}'")
            if not watching_path.is_dir():
                return f"Ошибка: {path} не является директорией"

            events_count = {
                "Created": 0,
                "Deleted": 0,
                "Modified/changed": 0,
                "Moved": 0,
            }
            events_list = []

            def get_statistica() -> Dict[str, Any]:
                files_count = 0
                dirs_count = 0
                total_size = 0
                for root, dirs, files in os.walk(watching_path):
                    dirs_count += len(dirs)
                    files_count += len(files)
                    for file in files:
                        file_path = Path(root) / file
                        try:
                            total_size += file_path.stat().st_size
                        except (OSError, PermissionError):
                            pass
                return {
                    "files": files_count,
                    "directories": dirs_count,
                    "total_size_bytes": total_size,
                }

            def handle_event(event_type: str, message: str, event: FileSystemEvent):
                events_count[event_type] += 1
                timestamp = datetime.now().strftime("%H:%M:%S %d-%m-%Y")
                event_info = {
                    "time": timestamp,
                    "type": event_type,
                    "message": message,
                    "path": event.src_path,
                }
                events_list.append(event_info)
                if details:
                    print(f"[{timestamp}] [{event_type}] {message}")

            class WatcherEventHandler(FileSystemEventHandler):
                def on_created(self, event: FileSystemEvent):
                    msg = f"Файл {event.src_path} создан" if not event.is_directory else f"Директория {event.src_path} создана"
                    handle_event("Created", msg, event)

                def on_deleted(self, event: FileSystemEvent):
                    msg = f"Файл {event.src_path} удален" if not event.is_directory else f"Директория {event.src_path} удалена"
                    handle_event("Deleted", msg, event)

                def on_modified(self, event: FileSystemEvent):
                    msg = f"Файл {event.src_path} изменен" if not event.is_directory else f"Директория {event.src_path} изменена"
                    handle_event("Modified/changed", msg, event)

                def on_moved(self, event: FileSystemEvent):
                    msg = f"Файл {event.src_path} перемещен" if not event.is_directory else f"Директория {event.src_path} перемещена"
                    handle_event("Moved", msg, event)

            if details:
                stats = get_statistica()
                print("\nСтатистика директории перед началом:")
                print(f"  Файлов: {stats['files']}")
                print(f"  Поддиректорий: {stats['directories']}")
                print(f"  Общий размер: {stats['total_size_bytes']} байт")

            event_handler = WatcherEventHandler()
            observer = Observer()
            observer.schedule(event_handler, str(watching_path), recursive=True)
            observer.start()

            if details:
                print(f"\nОтслеживание начато: {watching_path.resolve()}")
                print(f"Продолжительность: {'бесконечно' if duration is None else f'{duration} сек'}\n")

            try:
                if duration is not None:
                    time.sleep(duration)
                else:
                    while True:
                        time.sleep(1)
            except KeyboardInterrupt:
                if details:
                    print("\nОтслеживание прервано пользователем.")
            finally:
                observer.stop()
                observer.join()

            report_lines = [
                f"\n{'ОТЧЁТ ОТСЛЕЖИВАНИЙ'}",
                f"Директория: {watching_path.resolve()}",
                f"Всего событий: {sum(events_count.values())}",
                f"  Создано:        {events_count['Created']}",
                f"  Удалено:        {events_count['Deleted']}",
                f"  Изменено:       {events_count['Modified/changed']}",
                f"  Перемещено:     {events_count['Moved']}",
            ]

            if details and events_list:
                report_lines.append("Последние события:")
                for ev in events_list[-10:]:
                    report_lines.append(f"  [{ev['time']}] {ev['type']}: {ev['message']}")

            return "\n".join(report_lines)

        except Exception as e:
            return f"Произошла ошибка при отслеживании директории {path}: {e}"