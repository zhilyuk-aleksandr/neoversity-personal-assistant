"""Локальне зберігання обох книг у читабельному файлі JSON."""

import json
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from .address_book import AddressBook
from .notes import Note, NoteBook
from .record import Record

if os.name == "nt":
    import msvcrt
else:
    import fcntl


def data_directory():
    """Вибрати теку з налаштувань або домашню теку користувача."""
    path = os.environ.get("ASSISTANT_DATA_DIR")
    return (
        Path(path).expanduser()
        if path
        else Path.home() / ".personal_assistant"
    )


@contextmanager
def session_lock(directory):
    """Дозволити одному процесу редагувати книги у вибраній теці."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".session.lock").open("a+b") as handle:
        try:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise OSError(
                "Тека даних зайнята або недоступна для блокування."
            ) from error
        # Закриття дескриптора звільняє блокування, зокрема після переривання.
        yield


class Storage:
    """Завантаження, перевірка й атомарний запис стану помічника."""

    def __init__(self, directory):
        self.directory = directory
        self.path = directory / "assistant.json"

    def load(self):
        """Повернути книги й текст попередження у разі пошкодження файла."""
        contacts, notes = AddressBook(), NoteBook()
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return contacts, notes, ""
        try:
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Очікується об’єкт JSON.")
            if not all(
                isinstance(data[key], list) for key in ("contacts", "notes")
            ):
                raise ValueError("Очікуються списки контактів і нотаток.")
            for row in data["contacts"]:
                contacts.add(Record(**row))
            for row in data["notes"]:
                notes.add(Note(**row))
        except (ValueError, KeyError, TypeError, RecursionError):
            backup = self.directory / f"assistant-damaged-{uuid4().hex}.json"
            self.path.rename(backup)
            warning = (
                f"Файл даних пошкоджено. Оригінал збережено у {backup.name}."
            )
            return AddressBook(), NoteBook(), warning
        return contacts, notes, ""

    def save(self, contacts, notes):
        """Записати цілий стан у тимчасовий файл та замінити попередню
        версію.
        """
        data = {
            "contacts": [record.to_dict() for record in contacts.values()],
            "notes": [note.to_dict() for note in notes.values()],
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with NamedTemporaryFile(
                mode="w", dir=self.directory, encoding="utf-8", delete=False
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
