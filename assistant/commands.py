"""Синтаксис команд, обробники та повідомлення користувачеві."""

import re
import shlex
from copy import deepcopy
from functools import wraps
from typing import NamedTuple

from .fields import Address, Birthday, Email, InputError, Name, Phone
from .note_input import guided_note, note_arguments
from .notes import Note
from .record import Record
from .suggest import ALIASES, suggest
from .view import birthday_lines, contact_table


class Command(NamedTuple):
    """Аргументи, межі їх кількості та ознака зміни даних."""

    syntax: str
    minimum: int
    maximum: int | None
    writes: bool = False


COMMANDS = {
    "add-contact": Command(
        "ІМʼЯ [ТЕЛЕФОН [АДРЕСА]] [ПОЛЕ=ЗНАЧЕННЯ ...]", 1, None, True
    ),
    "edit-contact": Command(
        "ІМʼЯ ПОЛЕ=ЗНАЧЕННЯ [ПОЛЕ=ЗНАЧЕННЯ ...]", 2, None, True
    ),
    "delete-contact": Command("ІМʼЯ", 1, 1, True),
    "find-contact": Command("ЗАПИТ", 1, 1),
    "all-contacts": Command("", 0, 0),
    "add-phone": Command("ІМʼЯ НОМЕР", 2, 2, True),
    "edit-phone": Command("ІМʼЯ СТАРИЙ НОВИЙ", 3, 3, True),
    "delete-phone": Command("ІМʼЯ НОМЕР", 2, 2, True),
    "birthdays": Command("N [--within]", 1, 2),
    "add-note": Command("ЗАГОЛОВОК ТЕКСТ [ТЕГ ...]", 2, None, True),
    "edit-note": Command(
        "ЗАГОЛОВОК ТЕКСТ [ТЕГ ...] або ЗАГОЛОВОК tags=...", 2, None, True
    ),
    "delete-note": Command("ЗАГОЛОВОК", 1, 1, True),
    "find-note": Command("ЗАПИТ", 1, 1),
    "all-notes": Command("", 0, 0),
    "set-tags": Command("ЗАГОЛОВОК [ТЕГ ...]", 1, None, True),
    "add-tag": Command("ЗАГОЛОВОК ТЕГ", 2, 2, True),
    "delete-tag": Command("ЗАГОЛОВОК ТЕГ", 2, 2, True),
    "find-tag": Command("ТЕГ", 1, 1),
    "sort-notes": Command("", 0, 0),
    "help": Command("[КОМАНДА]", 0, 1),
    "exit": Command("", 0, 0),
}


# Розділ довідки та короткий опис людською мовою.
DESCRIPTIONS = {
    "add-contact": ("Контакти", "додати контакт (без аргументів — покроково)"),
    "edit-contact": (
        "Контакти",
        "змінити ім’я, адресу, email, день народження",
    ),
    "delete-contact": ("Контакти", "видалити контакт (з підтвердженням)"),
    "find-contact": (
        "Контакти",
        "знайти за частиною імені, телефону, email чи адреси",
    ),
    "all-contacts": ("Контакти", "усі контакти таблицею"),
    "add-phone": ("Контакти", "додати ще один телефон"),
    "edit-phone": ("Контакти", "замінити телефон на новий"),
    "delete-phone": ("Контакти", "видалити телефон"),
    "birthdays": (
        "Контакти",
        "дні народження через N днів (--within — протягом N днів)",
    ),
    "add-note": ("Нотатки", "додати нотатку (без аргументів — покроково)"),
    "edit-note": ("Нотатки", "змінити текст або теги"),
    "delete-note": ("Нотатки", "видалити нотатку (з підтвердженням)"),
    "find-note": ("Нотатки", "знайти за частиною заголовка чи тексту"),
    "all-notes": ("Нотатки", "усі нотатки"),
    "set-tags": ("Нотатки", "замінити всі теги нотатки"),
    "add-tag": ("Нотатки", "додати тег"),
    "delete-tag": ("Нотатки", "зняти тег"),
    "find-tag": ("Нотатки", "нотатки з цим тегом"),
    "sort-notes": ("Нотатки", "нотатки, згруповані за тегами"),
    "help": ("Інше", "довідка; help КОМАНДА — опис і приклади"),
    "exit": ("Інше", "зберегти дані й вийти (також close)"),
}


COMMAND_EXAMPLES = {
    "add-contact": (
        "Введіть add-contact без аргументів "
        "для покрокового введення в терміналі.",
        'add-contact Лада 0501234567 Київ',
        'add-contact "Олена Демо" phone=0501234567 '
        'address="Київ, вул. Сонячна 10"',
        "Доступні поля: phone, address, email, birthday.",
    ),
    "edit-contact": (
        'Введіть edit-contact "Олена Демо" для покрокових змін у терміналі.',
        'edit-contact "Олена Демо" address "Київ, вул. Сонячна 10", '
        'email user@example.com',
        'edit-contact "Олена Демо" email=user@example.com birthday=15.04.1995',
        "Доступні поля: name, phone, address, email, birthday.",
        "phone додає номер. Щоб замінити конкретний номер, "
        "введіть edit-phone.",
    ),
    "add-note": (
        "Введіть add-note для покрокового створення нотатки в терміналі.",
        'add-note "План демо" "Підготувати слайди" навчання демо',
        'add-note "План демо" text="Підготувати слайди" tags=навчання,демо',
    ),
    "edit-note": (
        'Введіть edit-note "План демо" для покрокових змін.',
        'edit-note "План демо" text="Показати команді" tags=демо,команда',
        'edit-note "План демо" tags=демо',
        'Список tags замінює попередні теги. tags="" очищає їх.',
    ),
    "delete-contact": (
        'delete-contact "Лада Зоряна"',
        "Помічник перепитає, чи справді видалити.",
    ),
    "find-contact": (
        "find-contact зоряна",
        "find-contact 050123",
        "find-contact example.com",
    ),
    "all-contacts": ("all-contacts",),
    "add-phone": ('add-phone "Лада Зоряна" 0501234567',),
    "edit-phone": ('edit-phone "Лада Зоряна" 0501234567 0507654321',),
    "delete-phone": ('delete-phone "Лада Зоряна" 0507654321',),
    "birthdays": (
        "birthdays 7 — у кого день народження рівно через 7 днів.",
        "birthdays 7 --within — усі дні народження "
        "протягом найближчих 7 днів.",
        "birthdays 0 — сьогоднішні іменинники.",
    ),
    "delete-note": (
        'delete-note "План демо"',
        "Помічник перепитає, чи справді видалити.",
    ),
    "find-note": ("find-note слайди",),
    "all-notes": ("all-notes",),
    "set-tags": (
        'set-tags "План демо" навчання демо',
        'set-tags "План демо" — прибрати всі теги.',
    ),
    "add-tag": ('add-tag "План демо" захист',),
    "delete-tag": ('delete-tag "План демо" захист',),
    "find-tag": ("find-tag навчання",),
    "sort-notes": (
        "sort-notes — групи за тегами, нотатки без тегів наприкінці.",
    ),
    "help": ("help", "help birthdays"),
    "exit": ("exit", "Також Ctrl+D або два Ctrl+C поспіль."),
}

# Чого спитати в терміналі, якщо команду ввели без потрібних аргументів.
ARGUMENT_PROMPTS = {
    "delete-contact": ("Який контакт видалити",),
    "find-contact": ("Кого шукаємо (ім’я, телефон, email чи адреса)",),
    "add-phone": ("Ім’я контакту", "Новий телефон"),
    "edit-phone": ("Ім’я контакту", "Який телефон замінити", "Новий телефон"),
    "delete-phone": ("Ім’я контакту", "Який телефон видалити"),
    "birthdays": ("Через скільки днів",),
    "delete-note": ("Яку нотатку видалити (заголовок)",),
    "find-note": ("Що шукаємо в нотатках",),
    "set-tags": ("Заголовок нотатки",),
    "add-tag": ("Заголовок нотатки", "Тег"),
    "delete-tag": ("Заголовок нотатки", "Тег"),
    "find-tag": ("Який тег",),
}
YES = {"т", "так", "y", "yes", "д", "да"}

# Пропускаємо текст у лапках та екрановані символи. Кома є роздільником
# лише перед наступним полем: «Київ, вул. Сонячна» залишається однією адресою.
CONTACT_COMMAS = re.compile(
    r''' "(?:\\.|[^"\\])*" | '[^']*' | \\.
       | (?P<separator>,) (?= \s*
           (?: [\w-]+= | (?:name|phone|address|email|birthday)(?:\s|$) )
       )
    ''',
    re.IGNORECASE | re.VERBOSE,
)


def split_contact_words(line):
    """Зберегти межі між полями, щоб розпізнати й пропущене перед комою
    значення.
    """
    words = []
    start = 0
    for match in CONTACT_COMMAS.finditer(line):
        if match.group("separator"):
            words.extend(shlex.split(line[start:match.start()]))
            words.append(None)
            start = match.end()
    words.extend(shlex.split(line[start:]))
    return words


def help_text(command=None):
    """Побудувати довідку зі спільного опису команд."""
    if command is not None:
        command = command.casefold()
        command = ALIASES.get(command, command)
        if command not in COMMANDS:
            return suggest(command, COMMANDS)
        usage = f"{command} {COMMANDS[command].syntax}".rstrip()
        text = DESCRIPTIONS[command][1]
        lines = [usage, f"  {text[0].upper()}{text[1:]}."]
        examples = COMMAND_EXAMPLES.get(command, ())
        if examples:
            lines.append("Приклади й пояснення:")
            lines.extend(f"  {example}" for example in examples)
        return "\n".join(lines)
    lines = ["Команди помічника"]
    width = max(map(len, COMMANDS)) + 2
    group = None
    for name in COMMANDS:
        section, text = DESCRIPTIONS[name]
        if section != group:
            group = section
            lines.append(section)
        lines.append(f"  {name.ljust(width)}{text}")
    lines.append(
        "Опис і приклади для будь-якої команди: help КОМАНДА, "
        "наприклад help add-contact."
    )
    lines.append(
        "Назви з пробілами беріть у подвійні лапки. Синоніми: add, new, close."
    )
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


def contact_fields(options, *, creating):
    """Прочитати короткий запис і пари поле=значення або поле значення."""
    allowed = ("phone", "address", "email", "birthday")
    if not creating:
        allowed += ("name",)
    short_fields = ("phone", "address") if creating else ()
    fields = {}
    phones = []
    tokens = iter(options)
    for token in tokens:
        if token is None:
            continue
        key, equals, value = token.partition("=")
        key = key.casefold()
        if short_fields and not equals and key not in allowed:
            key, value = short_fields[0], token
            short_fields = short_fields[1:]
        else:
            short_fields = ()
            if key not in allowed:
                raise InputError(
                    f"Невідоме поле «{key}». "
                    f"Доступні поля: {', '.join(allowed)}."
                )
            if not equals:
                value = next(tokens, None)
                if value is None:
                    raise InputError(f"Вкажіть значення поля {key}.")
        if key == "phone":
            phones.append(value)
        elif key in fields:
            raise InputError(f"Поле {key} повторюється.")
        else:
            fields[key] = value
    return phones, fields


def guided_contact(contacts, command, args, ask):
    """Зібрати поля в діалозі, щоб передати їх звичайному обробнику
    однією командою.
    """
    creating = command == "add-contact"
    record = None
    result = []
    intro = "Enter пропускає поле. /cancel скасовує введення.\n"
    if not creating:
        name = (
            args[0]
            if args
            else ask(intro + "Який контакт редагувати? ").strip()
        )
        if name == "/cancel":
            return "Скасовано."
        record = contacts.get_record(name)
        result.append(str(record.name))
    questions = (
        ("name", "Ім’я (обов’язково)" if creating else "Нове ім’я", Name),
        ("phone", "Телефон" if creating else "Додатковий телефон", Phone),
        ("address", "Адреса або місто", Address),
        ("email", "Email", Email),
        ("birthday", "День народження (ДД.ММ.РРРР)", Birthday),
    )
    for key, label, field_type in questions:
        while True:
            value = ask(intro + label + ": ").strip()
            intro = ""
            if value == "/cancel":
                return "Скасовано."
            if not value and (not creating or key != "name"):
                break
            try:
                field = field_type(value)
                if key == "name" and value.casefold() in contacts:
                    if contacts.get_record(value) is not record:
                        raise InputError("Контакт із таким іменем уже є.")
                if (
                    key == "phone"
                    and record is not None
                    and field in record.phones
                ):
                    raise InputError("Такий телефон уже є в контакті.")
            except InputError as error:
                intro = f"{error}\n"
                continue
            result.append(
                value if creating and key == "name" else f"{key}={value}"
            )
            break
    if not creating and len(result) == 1:
        return "Змін не внесено."
    return result


class Actions:
    """Обробники дій над двома книгами помічника."""

    def __init__(self, contacts, notes):
        self.contacts = contacts
        self.notes = notes

    def add_contact(self, name, *options):
        """Розібрати параметри і створити контакт."""
        phones, fields = contact_fields(options, creating=True)
        record = Record(name, phones, **fields)
        self.contacts.add(record)
        return f"Контакт «{record.name}» додано."

    def edit_contact(self, name, *options):
        """Оновити поля вибраного контакту в межах однієї команди."""
        record = self.contacts.get_record(name)
        phones, fields = contact_fields(options, creating=False)
        for field, value in fields.items():
            self.contacts.edit(str(record.name), field, value)
        for phone in phones:
            record.add_phone(phone)
        return "Контакт оновлено."

    def delete_contact(self, name):
        """Видалити контакт."""
        self.contacts.remove(name)
        return "Контакт видалено."

    def find_contact(self, query):
        """Показати знайдені контакти."""
        found = self.contacts.find(query)
        return (
            cards(found)
            if found
            else f"За запитом «{query}» контактів не знайдено."
        )

    def all_contacts(self):
        """Показати всі контакти таблицею."""
        return contact_table(self.contacts.values())

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
            raise InputError(
                "Введіть цілу кількість днів від нуля."
            ) from error
        if mode not in (None, "--within"):
            raise InputError("Для пошуку за періодом використайте --within.")
        within = mode == "--within"
        matches = self.contacts.birthdays(days, within=within)
        return birthday_lines(matches, days, within)

    def add_note(self, title, text, tags=None):
        """Додати нотатку з необов’язковими тегами."""
        note = Note(title, text, tags or ())
        self.notes.add(note)
        return f"Нотатку «{note.title}» додано."

    def edit_note(self, title, text, tags=None):
        """Оновити передані текст і теги в межах однієї команди."""
        note = self.notes.get_note(title)
        if text is not None:
            note.edit(text)
        if tags is not None:
            note.set_tags(tags)
        return "Нотатку оновлено."

    def delete_note(self, title):
        """Видалити нотатку."""
        self.notes.remove(title)
        return "Нотатку видалено."

    def find_note(self, query):
        """Показати нотатки за частиною заголовка або тексту."""
        found = self.notes.find(query)
        return (
            cards(found)
            if found
            else f"За запитом «{query}» нотаток не знайдено."
        )

    def all_notes(self):
        """Показати всі нотатки."""
        return (
            cards(self.notes.values())
            if self.notes
            else "Нотаток ще немає. Додайте першу: add-note"
        )

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
        found = self.notes.by_tag(tag)
        return cards(found) if found else f"Нотаток з тегом «{tag}» немає."

    def sort_notes(self):
        """Показати заголовки нотаток, згруповані за тегами."""
        lines = []
        for tag, notes in self.notes.groups():
            lines.append(
                f"{tag or '(без тегів)'}: "
                + ", ".join(note.title for note in notes)
            )
        return "\n".join(lines) or "Нотаток ще немає. Додайте першу: add-note"


class Session:
    """Обробка команд і публікація змін після успішного запису."""

    def __init__(self, contacts, notes, storage):
        self.actions = Actions(contacts, notes)
        self.storage = storage
        self.closed = False

    @input_error
    def execute(self, line, *, ask=None):
        """Перевірити команду, виконати її та повернути відповідь
        користувачеві.
        """
        try:
            words = shlex.split(line)
        except ValueError as error:
            raise InputError(
                "Перевірте парність лапок і завершення рядка."
            ) from error
        if not words:
            return ""
        name = words[0].casefold()
        name = ALIASES.get(name, name)
        if name not in COMMANDS:
            return suggest(name, COMMANDS)
        if name in ("add-contact", "edit-contact") and "," in line:
            words = split_contact_words(line)
        spec = COMMANDS[name]
        args = words[1:]
        if ask is not None and (
            (name == "add-contact" and not args)
            or (name == "edit-contact" and len(args) <= 1)
        ):
            args = guided_contact(self.actions.contacts, name, args, ask)
        elif name in ("add-note", "edit-note"):
            if len(args) >= 2:
                args = note_arguments(line)
            elif ask is not None:
                args = guided_note(self.actions.notes, name, args, ask)
        if isinstance(args, str):
            return args
        if (
            ask is not None
            and name in ARGUMENT_PROMPTS
            and len(args) < spec.minimum
        ):
            args = list(args)
            for label in ARGUMENT_PROMPTS[name][len(args):spec.minimum]:
                value = ask(f"{label}: ").strip()
                if not value or value == "/cancel":
                    return "Скасовано."
                args.append(value)
        if len(args) < spec.minimum or (
            spec.maximum is not None and len(args) > spec.maximum
        ):
            raise InputError(f"Формат: {name} {spec.syntax}".rstrip())
        if name == "help":
            return help_text(*args)
        if name == "exit":
            self.closed = True
            return ""
        if ask is not None and name in ("delete-contact", "delete-note"):
            if name == "delete-contact":
                record = self.actions.contacts.get_record(args[0])
                what = f"контакт «{record.name}»"
            else:
                what = (
                    f"нотатку «{self.actions.notes.get_note(args[0]).title}»"
                )
            if ask(f"Видалити {what}? (т/Н): ").strip().casefold() not in YES:
                return "Скасовано, нічого не видалено."
        # Копія зберігає попередній стан на випадок помилки запису.
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
