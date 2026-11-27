"""Адресна книга з пошуком та календарем днів народження."""

import re
from collections import UserDict
from datetime import date, timedelta

from .fields import Address, Birthday, Email, InputError, Name, required_text
from .record import optional_field


class AddressBook(UserDict):
    """Колекція контактів з унікальними іменами без урахування регістру."""

    @staticmethod
    def _key(name):
        """Єдиний ключ для імені: casefold — єдина нормалізація ключів
        книги.
        """
        return str(name).casefold()

    def __setitem__(self, name, record):
        """Записати контакт, не допускаючи дублів і невідповідного ключа."""
        key = self._key(name)
        if key != self._key(record.name):
            raise InputError("Ключ має збігатися з іменем контакту.")
        if key in self.data and self.data[key] is not record:
            raise InputError("Контакт із таким іменем уже є.")
        self.data[key] = record

    def __getitem__(self, name):
        return self.data[self._key(name)]

    def __delitem__(self, name):
        del self.data[self._key(name)]

    def __contains__(self, name):
        return self._key(name) in self.data

    def add(self, record):
        """Додати контакт з унікальним іменем."""
        if record.name in self:
            raise InputError("Контакт із таким іменем уже є.")
        self[record.name] = record

    def get_record(self, name):
        """Знайти один контакт за точним іменем."""
        key = required_text(name, "ім’я").casefold()
        if key not in self.data:
            raise InputError("Контакт із таким іменем не знайдено.")
        return self.data[key]

    def remove(self, name):
        """Видалити вибраний контакт."""
        record = self.get_record(name)
        del self.data[str(record.name).casefold()]

    def edit(self, name, field, value):
        """Перейменувати контакт або змінити одне необов’язкове поле."""
        record = self.get_record(name)
        if field == "name":
            new_name = Name(value)
            key = str(new_name).casefold()
            if key in self.data and self.data[key] is not record:
                raise InputError("Контакт із таким іменем уже є.")
            self.remove(name)
            record.name = new_name
            self.data[key] = record
            return
        types = {"email": Email, "address": Address, "birthday": Birthday}
        if field not in types:
            raise InputError(
                "Виберіть поле name, email, address або birthday."
            )
        setattr(record, field, optional_field(types[field], value))

    def find(self, query):
        """Шукати частину тексту або номера в усіх полях контакту."""
        query = required_text(query, "запит").casefold()
        digits = re.sub(r"[\s-]", "", query).removeprefix("+38")
        result = []
        for record in self.values():
            fields = (
                record.name,
                record.address,
                record.email,
                record.birthday,
            )
            if any(
                query in str(field).casefold() for field in fields if field
            ):
                result.append(record)
            elif digits.isascii() and digits.isdigit():
                if any(digits in str(phone) for phone in record.phones):
                    result.append(record)
        return result

    def birthdays(self, days, within=False, today=None):
        """Повернути пари (дата, контакт) на точну дату або за період включно.

        Для кожного контакту в періоді враховується одне найближче святкування.
        Для 29 лютого у невисокосному році святкування припадає на 28 лютого.
        """
        today = today or date.today()
        if type(days) is not int or days < 0:
            raise InputError(
                "Кількість днів має бути цілим невід’ємним числом."
            )
        try:
            target = today + timedelta(days=days)
        except OverflowError as error:
            raise InputError("Запит виходить за межі календаря.") from error
        matches = []
        for record in self.values():
            if not record.birthday:
                continue
            birthday = record.birthday
            if within:
                event = birthday.in_year(today.year)
                if event < today:
                    if today.year == target.year:
                        continue
                    event = birthday.in_year(today.year + 1)
                if event <= target:
                    matches.append((event, record))
            elif birthday.in_year(target.year) == target:
                matches.append((target, record))
        return sorted(
            matches, key=lambda item: (item[0], str(item[1].name).casefold())
        )
