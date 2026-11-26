"""Перевірки полів, операцій з контактами та календаря."""

import unittest
from datetime import date, timedelta

from assistant.address_book import AddressBook
from assistant.fields import Address, Birthday, Email, InputError, Name, Phone
from assistant.record import Record
from assistant.view import contact_table


class ContactTests(unittest.TestCase):
    """Приклади створення, редагування й пошуку контактів."""

    def test_phone_formats(self):
        """Префікс, дефіси та пробіли дають один номер."""
        for raw in ("0501234567", "+38 050-123-45-67"):
            self.assertEqual(str(Phone(raw)), "0501234567")
        for raw in ("125", "+1 0501234567", "050abc4567", "05012345678", ""):
            with self.subTest(raw=raw), self.assertRaises(InputError):
                Phone(raw)

    def test_email(self):
        """Пошта повинна мати коректні частини адреси."""
        self.assertEqual(str(Email(" user@example.com ")), "user@example.com")
        for raw in ("user@", "@example.com", "a b@example.com", "a@-example.com", "a..b@ex.ua"):
            with self.subTest(raw=raw), self.assertRaises(InputError):
                Email(raw)

    def test_fields(self):
        """Ім’я обов’язкове, адресу можна пропустити."""
        for field in (Name, Address):
            for value in ("   ", None, 12):
                with self.subTest(field=field.__name__, value=value):
                    with self.assertRaises(InputError):
                        field(value)
        self.assertEqual(str(Name("  Лада Зоряна ")), "Лада Зоряна")
        self.assertEqual(str(Address("  вул. Зоряна 2 ")), "вул. Зоряна 2")
        record = Record("Лада", address=" ", email=" ", birthday=" ")
        self.assertIsNone(record.address)
        self.assertIsNone(record.email)
        self.assertIsNone(record.birthday)

    def test_dates(self):
        """Дата реальна, в точному форматі та не в майбутньому."""
        self.assertEqual(str(Birthday("29.02.2000")), "29.02.2000")
        future = (date.today() + timedelta(days=1)).strftime("%d.%m.%Y")
        for raw in ("29.02.2001", "1.1.2000", "2000-01-01", future):
            with self.subTest(raw=raw), self.assertRaises(InputError):
                Birthday(raw)

    def test_contact_search(self):
        """Пошук працює за кожним полем і без урахування регістру."""
        book = AddressBook()
        record = Record("Лада", ["0501234567"], "вул. Зоряна 2", "user@example.com", "03.04.2000")
        book.add(record)
        for query in ("ЛАД", "  +38 050-123  ", "123-45", "ЗОРЯ", "EXAMPLE", "03.04"):
            with self.subTest(query=query):
                self.assertEqual(book.find(query), [record])
        self.assertEqual(book.find("немає"), [])

    def test_edit_and_remove(self):
        """Перейменування оновлює ключ, а видалення прибирає запис."""
        book = AddressBook()
        book.add(Record("Лада"))
        book.edit("лада", "name", "Зоря")
        book.edit("Зоря", "email", "user@example.com")
        book.edit("Зоря", "address", "вул. Тиха 3")
        book.edit("Зоря", "birthday", "01.01.2000")
        book.edit("Зоря", "address", "")
        self.assertIsNone(book.get_record("зоря").address)
        self.assertEqual(str(book.get_record("зоря").birthday), "01.01.2000")
        self.assertFalse(book.find("Лада"))
        book.remove("Зоря")
        self.assertFalse(book)

    def test_duplicates_and_bad_edits(self):
        """Помилкові зміни зберігають попередній стан."""
        book = AddressBook()
        book.add(Record("Лада", email="user@example.com"))
        book.add(Record("Соня"))
        with self.assertRaises(InputError):
            book.add(Record("лАДа"))
        with self.assertRaises(InputError):
            book.edit("Лада", "name", "Соня")
        with self.assertRaises(InputError):
            book.edit("Лада", "email", "помилка")
        self.assertEqual(str(book.get_record("лада").email), "user@example.com")
        self.assertEqual(str(book.get_record("лада").name), "Лада")
        self.assertEqual(sorted(book.data), ["лада", "соня"])

    def test_dict_api_keeps_rules(self):
        """Запис через словниковий інтерфейс не обходить правила книги."""
        book = AddressBook()
        record = Record("Лада")
        book["ЛАДА"] = record
        self.assertIn("лада", book)
        self.assertIs(book["Лада"], record)
        for action in (
            lambda: book.add(Record("лада")),
            lambda: book.__setitem__("Лада", Record("лАДа")),
            lambda: book.__setitem__("Соня", Record("Лада")),
            lambda: book.update({"Лада": Record("лада")}),
        ):
            with self.subTest(action=action), self.assertRaises(InputError):
                action()
        self.assertEqual(len(book), 1)
        del book["лада"]
        self.assertNotIn("Лада", book)

    def test_record_round_trip(self):
        """Record(**to_dict()) відновлює контакт без втрат."""
        for record in (
            Record("Лада", ["0501234567", "+38 050-765-43-21"], "вул. Зоряна 2",
                   "user@example.com", "29.02.2000"),
            Record("Соня"),
        ):
            with self.subTest(name=str(record.name)):
                data = record.to_dict()
                self.assertEqual(Record(**data).to_dict(), data)
        self.assertEqual(
            Record("Соня").to_dict(),
            {"name": "Соня", "phones": [], "address": None, "email": None, "birthday": None},
        )

    def test_phones(self):
        """Контакт може мати декілька різних нормалізованих номерів."""
        record = Record("Лада", ["0501234567"])
        record.add_phone("0507654321")
        with self.assertRaises(InputError):
            record.change_phone("0507654321", "0501234567")
        with self.assertRaises(InputError):
            record.change_phone("0507654321", "x")
        record.change_phone("0507654321", "0500000001")
        record.delete_phone("+38 050-123-45-67")
        self.assertEqual([str(phone) for phone in record.phones], ["0500000001"])

    def test_exact_and_period(self):
        """Через сім днів і протягом тижня дають різні списки."""
        book = AddressBook()
        book.add(Record("Зоря", birthday="02.12.2000"))
        book.add(Record("Лада", birthday="28.11.2000"))
        book.add(Record("Соня", birthday="25.11.2000"))
        book.add(Record("Ада", birthday="03.12.2000"))
        book.add(Record("Тая"))
        today = date(2026, 11, 25)
        matches = book.birthdays(7, today=today)
        self.assertEqual([str(record.name) for _, record in matches], ["Зоря"])
        matches = book.birthdays(7, within=True, today=today)
        self.assertEqual([str(record.name) for _, record in matches], ["Соня", "Лада", "Зоря"])

    def test_birthdays_rejects_non_integer_days(self):
        """Дробове число, bool та не числа відхиляються, а 0 працює."""
        book = AddressBook()
        today = date(2026, 11, 25)
        for days in (1.5, True, False, 2.0, "1", None, -1):
            for within in (False, True):
                with self.subTest(days=days, within=within):
                    with self.assertRaises(InputError):
                        book.birthdays(days, within=within, today=today)
        self.assertEqual(book.birthdays(0, today=today), [])

    def test_table_fits_width_with_many_phones(self):
        """Таблиця вкладається в ширину, а картка показує всі номери."""
        phones = ["0501234567", "0507654321", "0500000001", "0500000002"]
        record = Record("Лада Зоряна", phones, "вул. Зоряна 2, Київ", "user@example.com", "03.04.2000")
        for width in (70, 80, 100):
            with self.subTest(width=width):
                lines = contact_table([record], width=width).splitlines()
                self.assertLessEqual(max(map(len, lines)), width)
        narrow = contact_table([record], width=70)
        self.assertIn("0501234567", narrow)
        self.assertIn("+3", narrow)
        self.assertEqual(len(record.phones), 4)
        for phone in phones:
            self.assertIn(phone, str(record))
        wide = contact_table([record], width=200)
        for phone in phones:
            self.assertIn(phone, wide)
        self.assertNotIn("+3", wide)

    def test_year_and_leap(self):
        """Новий рік, високосний рік і сьогодні обробляються явно."""
        book = AddressBook()
        book.add(Record("Зоря", birthday="01.01.2000"))
        book.add(Record("Лада", birthday="29.02.2000"))
        for today, days, name, target in (
            (date(2026, 12, 31), 1, "Зоря", date(2027, 1, 1)),
            (date(2025, 2, 28), 0, "Лада", date(2025, 2, 28)),
            (date(2024, 2, 28), 1, "Лада", date(2024, 2, 29)),
        ):
            with self.subTest(today=today):
                matches = book.birthdays(days, today=today)
                self.assertEqual([(d, str(r.name)) for d, r in matches], [(target, name)])

    def test_period_year_and_leap(self):
        """Період через Новий рік і 29 лютого повертає дати за порядком."""
        book = AddressBook()
        book.add(Record("Зоря", birthday="01.01.2000"))
        book.add(Record("Лада", birthday="29.02.2000"))
        book.add(Record("Соня", birthday="31.12.1999"))
        book.add(Record("Тая", birthday="02.01.2000"))
        for today, days, expected in (
            (date(2026, 12, 30), 3, [("Соня", date(2026, 12, 31)), ("Зоря", date(2027, 1, 1)),
                                     ("Тая", date(2027, 1, 2))]),
            (date(2026, 12, 31), 0, [("Соня", date(2026, 12, 31))]),
            (date(2025, 2, 27), 2, [("Лада", date(2025, 2, 28))]),
            (date(2024, 2, 27), 2, [("Лада", date(2024, 2, 29))]),
            (date(2025, 3, 1), 30, []),
        ):
            with self.subTest(today=today, days=days):
                matches = book.birthdays(days, within=True, today=today)
                self.assertEqual([(str(r.name), d) for d, r in matches], expected)
