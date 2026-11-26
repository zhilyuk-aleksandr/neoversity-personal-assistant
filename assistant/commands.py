"""Синтаксис команд, обробники та повідомлення користувачеві."""

import shlex
from copy import deepcopy
from functools import wraps
from typing import NamedTuple

from .fields import InputError
from .notes import Note
from .record import Record
from .suggest import ALIASES, suggest


class Command(NamedTuple):
    """Аргументи, межі їх кількості та ознака зміни даних."""

    syntax: str
    minimum: int
    maximum: int | None
    writes: bool = False


COMMANDS = {
    "add-contact": Command(
        "ІМʼЯ [phone=...] [address=...] [email=...] [birthday=...]", 1, None, True
    ),
    "edit-contact": Command("ІМʼЯ ПОЛЕ ЗНАЧЕННЯ", 3, 3, True),
    "delete-contact": Command("ІМʼЯ", 1, 1, True),
    "find-contact": Command("ЗАПИТ", 1, 1),
    "all-contacts": Command("", 0, 0),
    "add-phone": Command("ІМʼЯ НОМЕР", 2, 2, True),
    "edit-phone": Command("ІМʼЯ СТАРИЙ НОВИЙ", 3, 3, True),
    "delete-phone": Command("ІМʼЯ НОМЕР", 2, 2, True),
    "birthdays": Command("N [--within]", 1, 2),
    "add-note": Command("ЗАГОЛОВОК ТЕКСТ [ТЕГ ...]", 2, None, True),
    "edit-note": Command("ЗАГОЛОВОК ТЕКСТ", 2, 2, True),
    "delete-note": Command("ЗАГОЛОВОК", 1, 1, True),
    "find-note": Command("ЗАПИТ", 1, 1),
    "all-notes": Command("", 0, 0),
    "set-tags": Command("ЗАГОЛОВОК [ТЕГ ...]", 1, None, True),
    "add-tag": Command("ЗАГОЛОВОК ТЕГ", 2, 2, True),
    "delete-tag": Command("ЗАГОЛОВОК ТЕГ", 2, 2, True),
    "find-tag": Command("ТЕГ", 1, 1),
    "sort-notes": Command("", 0, 0),
    "help": Command("", 0, 0),
    "exit": Command("", 0, 0),
}


def help_text():
    """Побудувати довідку зі спільного опису команд."""
    lines = ["Команди помічника"]
    lines.extend(f"  {name} {cmd.syntax}".rstrip() for name, cmd in COMMANDS.items())
    lines.append("Назви з пробілами беріть у подвійні лапки. Синоніми: add, new, close.")
    return "\n".join(lines)


def input_error(handler):
    """Показати причину помилки введення й продовжити діалог."""
    @wraps(handler)
    def wrapped(*args, **kwargs):
        """Перетворити виняток перевірки на повідомлення користувачеві."""
        try:
            return handler(*args, **kwargs)
        except InputError as error:
            return f"Помилка: {error}"
    return wrapped


def cards(items):
    """Вивести записи окремими картками."""
    return "\n\n".join(map(str, items)) or "Записів не знайдено."


class Actions:
    """Обробники дій над двома книгами помічника."""

    def __init__(self, contacts, notes):
        self.contacts = contacts
        self.notes = notes

    def add_contact(self, name, *options):
        """Розібрати параметри і створити контакт."""
        fields = {}
        phones = []
        for option in options:
            key, separator, value = option.partition("=")
            if not separator or key not in ("phone", "email", "address", "birthday"):
                raise InputError("Введіть поле у вигляді phone=, email=, address= або birthday=.")
            if key == "phone":
                phones.append(value)
            elif key in fields:
                raise InputError(f"Поле {key} повторюється.")
            else:
                fields[key] = value
        record = Record(name, phones, **fields)
        self.contacts.add(record)
        return f"Контакт «{record.name}» додано."

    def edit_contact(self, name, field, value):
        """Змінити одне поле вибраного контакту."""
        self.contacts.edit(name, field, value)
        return "Контакт оновлено."

    def delete_contact(self, name):
        """Видалити контакт."""
        self.contacts.remove(name)
        return "Контакт видалено."

    def find_contact(self, query):
        """Показати знайдені контакти."""
        return cards(self.contacts.find(query))

    def all_contacts(self):
        """Показати всі контакти."""
        return cards(self.contacts.values())

    def add_phone(self, name, phone):
        """Додати номер контакту."""
        self.contacts.get_record(name).add_phone(phone)
        return "Телефон додано."

    def edit_phone(self, name, old, new):
        """Виправити наявний номер контакту."""
        self.contacts.get_record(name).change_phone(old, new)
        return "Телефон оновлено."

    def delete_phone(self, name, phone):
        """Видалити телефон з контакту."""
        self.contacts.get_record(name).delete_phone(phone)
        return "Телефон видалено."

    def birthdays(self, count, mode=None):
        """Показати дні народження через N днів або протягом періоду."""
        try:
            days = int(count)
        except ValueError as error:
            raise InputError("Введіть цілу кількість днів від нуля.") from error
        if mode not in (None, "--within"):
            raise InputError("Для пошуку за періодом використайте --within.")
        matches = self.contacts.birthdays(days, within=mode == "--within")
        return "\n".join(f"{day:%d.%m.%Y} — {item.name}" for day, item in matches) or (
            "Днів народження не знайдено."
        )

    def add_note(self, title, text, *tags):
        """Додати нотатку з необов’язковими тегами."""
        note = Note(title, text, tags)
        self.notes.add(note)
        return f"Нотатку «{note.title}» додано."

    def edit_note(self, title, text):
        """Змінити текст нотатки."""
        self.notes.get_note(title).edit(text)
        return "Нотатку оновлено."

    def delete_note(self, title):
        """Видалити нотатку."""
        self.notes.remove(title)
        return "Нотатку видалено."

    def find_note(self, query):
        """Показати нотатки за частиною заголовка або тексту."""
        return cards(self.notes.find(query))

    def all_notes(self):
        """Показати всі нотатки."""
        return cards(self.notes.values())

    def set_tags(self, title, *tags):
        """Замінити весь список тегів."""
        self.notes.get_note(title).set_tags(tags)
        return "Теги оновлено."

    def add_tag(self, title, tag):
        """Додати тег до нотатки."""
        self.notes.get_note(title).add_tag(tag)
        return "Тег додано."

    def delete_tag(self, title, tag):
        """Зняти тег з нотатки."""
        self.notes.get_note(title).remove_tag(tag)
        return "Тег видалено."

    def find_tag(self, tag):
        """Знайти нотатки за точним тегом."""
        return cards(self.notes.by_tag(tag))

    def sort_notes(self):
        """Показати заголовки нотаток, згруповані за тегами."""
        lines = []
        for tag, notes in self.notes.groups():
            lines.append(f"{tag or '(без тегів)'}: " + ", ".join(note.title for note in notes))
        return "\n".join(lines) or "Записів не знайдено."


class Session:
    """Обробка команд і публікація змін після успішного запису."""

    def __init__(self, contacts, notes, storage):
        self.actions = Actions(contacts, notes)
        self.storage = storage
        self.closed = False

    @input_error
    def execute(self, line):
        """Перевірити команду, виконати її та повернути відповідь користувачеві."""
        try:
            words = shlex.split(line)
        except ValueError as error:
            raise InputError("Перевірте парність лапок і завершення рядка.") from error
        if not words:
            return ""
        name = words[0].casefold()
        name = ALIASES.get(name, name)
        if name not in COMMANDS:
            return suggest(name, COMMANDS)
        spec = COMMANDS[name]
        args = words[1:]
        if len(args) < spec.minimum or (spec.maximum is not None and len(args) > spec.maximum):
            raise InputError(f"Формат: {name} {spec.syntax}".rstrip())
        if name == "help":
            return help_text()
        if name == "exit":
            self.closed = True
            return ""
        # Копія ізолює незбережені зміни, якщо запис на диск завершиться помилкою.
        actions = deepcopy(self.actions) if spec.writes else self.actions
        handler = getattr(actions, name.replace("-", "_"))
        reply = handler(*args)
        if spec.writes:
            try:
                self.storage.save(actions.contacts, actions.notes)
            except OSError as error:
                return f"Не вдалося зберегти зміну: {error}. Спробуйте ще раз."
            self.actions = actions
        return reply
