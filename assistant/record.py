"""Запис адресної книги, що поєднує перевірені поля."""

from .fields import Address, Birthday, Email, InputError, Name, Phone


def optional_field(field_type, value):
    """Повернути поле або пропустити порожнє необов’язкове значення."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return field_type(value)


class Record:
    """Контакт з іменем, кількома телефонами та необов’язковими полями."""

    def __init__(
        self, name, phones=(), address=None, email=None, birthday=None
    ):
        self.name = Name(name)
        self.address = optional_field(Address, address)
        self.email = optional_field(Email, email)
        self.birthday = optional_field(Birthday, birthday)
        if not isinstance(phones, (list, tuple)):
            raise InputError("Телефони мають бути списком.")
        self.phones = []
        for phone in phones:
            self.add_phone(phone)

    def add_phone(self, value):
        """Додати новий номер після нормалізації."""
        phone = Phone(value)
        if phone in self.phones:
            raise InputError("Такий телефон уже є в контакті.")
        self.phones.append(phone)

    def _phone_index(self, value):
        phone = Phone(value)
        if phone not in self.phones:
            raise InputError("У контакті немає такого телефону.")
        return self.phones.index(phone)

    def change_phone(self, old, new):
        """Замінити наявний телефон, зберігаючи порядок номерів."""
        index = self._phone_index(old)
        phone = Phone(new)
        if phone != self.phones[index] and phone in self.phones:
            raise InputError("Такий телефон уже є в контакті.")
        self.phones[index] = phone

    def delete_phone(self, value):
        """Видалити вказаний телефон."""
        self.phones.pop(self._phone_index(value))

    def to_dict(self):
        """Підготувати прості значення для запису у JSON."""
        return {
            "name": str(self.name),
            "phones": [str(phone) for phone in self.phones],
            "address": str(self.address) if self.address else None,
            "email": str(self.email) if self.email else None,
            "birthday": str(self.birthday) if self.birthday else None,
        }

    def __str__(self):
        phones = ", ".join(map(str, self.phones)) or "—"
        return (
            f"{self.name}\n  Телефони: {phones}\n  Email: {self.email or '—'}"
            f"\n  Адреса: {self.address or '—'}"
            f"\n  День народження: {self.birthday or '—'}"
        )
