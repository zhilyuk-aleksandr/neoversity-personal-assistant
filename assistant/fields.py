"""Поля контакту та спільні правила перевірки введеного тексту."""

import re
from datetime import date, datetime


class InputError(ValueError):
    """Помилка у значенні поля або аргументах команди."""


def required_text(value, label):
    """Повернути очищений текст із принаймні одним видимим символом."""
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"Поле «{label}» має містити текст.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise InputError(f"Поле «{label}» містить пошкоджений символ.") from error
    return value.strip()


class Field:
    """Текстове поле запису адресної книги."""

    label = "значення"

    def __init__(self, value):
        self.value = required_text(value, self.label)

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if type(self) is not type(other):
            return NotImplemented
        return self.value == other.value

    def __repr__(self):
        return f"{type(self).__name__}({str(self)!r})"


class Name(Field):
    """Ім’я для відображення та ідентифікації контакту."""

    label = "ім’я"


class Address(Field):
    """Поштова адреса у довільній текстовій формі."""

    label = "адреса"


class Phone(Field):
    """Десятизначний номер з необов’язковим префіксом +38."""

    label = "телефон"

    def __init__(self, value):
        super().__init__(value)
        compact = re.sub(r"[\s-]", "", self.value).removeprefix("+38")
        if not re.fullmatch(r"[0-9]{10}", compact):
            raise InputError("Введіть 10 цифр телефону, наприклад 0501234567.")
        self.value = compact


class Email(Field):
    """Адреса електронної пошти з іменем та доменом."""

    label = "email"
    pattern = re.compile(
        r"[A-Za-z0-9_%+-]+(?:\.[A-Za-z0-9_%+-]+)*@"
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,63}"
    )

    def __init__(self, value):
        super().__init__(value)
        if not self.pattern.fullmatch(self.value):
            raise InputError("Перевірте email, наприклад user@example.com.")


class Birthday(Field):
    """Дата народження та дата святкування в конкретному році."""

    label = "день народження"

    def __init__(self, value):
        super().__init__(value)
        if not re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", self.value):
            raise InputError("Введіть дату у форматі DD.MM.YYYY.")
        try:
            self.date = datetime.strptime(self.value, "%d.%m.%Y").date()
        except ValueError as error:
            raise InputError("Такої календарної дати не існує.") from error
        if self.date > date.today():
            raise InputError("Дата народження не може бути в майбутньому.")

    def in_year(self, year):
        """Для 29 лютого у невисокосному році повернути 28 лютого."""
        try:
            return self.date.replace(year=year)
        except ValueError:
            return date(year, 2, 28)
