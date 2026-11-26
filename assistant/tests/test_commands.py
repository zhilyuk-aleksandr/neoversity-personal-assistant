"""Перевірки команд із книгами в пам’яті."""

import unittest
from unittest.mock import Mock

from assistant.address_book import AddressBook
from assistant.commands import Session
from assistant.notes import NoteBook


class MemoryStorage:
    """Зафіксувати виклики збереження без створення файлів."""

    def __init__(self):
        self.saved = []

    def save(self, contacts, notes):
        """Запам’ятати знімок книг після команди зміни."""
        self.saved.append((contacts, notes))


class CommandTests(unittest.TestCase):
    """Перевірити відповіді команд і стан сеансу."""

    def setUp(self):
        """Підготувати порожні книги."""
        self.store = MemoryStorage()
        self.session = Session(AddressBook(), NoteBook(), self.store)

    def test_input_errors(self):
        """Хибний ввід дає підказку, після нього приймається наступна команда."""
        invalid = [
            "find-contact",
            'add-contact "Лада',
            'add-contact " "',
            "new Лада phone=123",
            "new Лада email=помилка",
            "new Лада birthday=31.02.2000",
            "new Лада topic=тест",
            "new Лада email=user@example.com email=user@example.com",
            'add-note План " "',
            "birthdays -1",
            "birthdays місяць",
            "birthdays 7 точно",
            "exit зараз",
            "birthdays 999999999999999999",
        ]
        for command in invalid:
            with self.subTest(command=command):
                self.assertIn("Помилка:", self.session.execute(command))
        self.assertFalse(self.session.closed)
        self.assertEqual(self.store.saved, [])
        self.assertIn("додано", self.session.execute("new Лада"))
        self.assertIn("Лада", self.session.execute("all-contacts"))
        self.assertEqual(self.session.execute("   "), "")
        self.assertEqual(len(self.store.saved), 1)

    def test_suggestion_and_aliases(self):
        """Описка пропонує команду, синоніми виконуються."""
        self.assertIn("«add-contact»?", self.session.execute("ad-contact"))
        self.assertIn("help", self.session.execute("жжжжж"))
        self.assertIn("додано", self.session.execute("add Лада"))
        self.session.execute("close")
        self.assertTrue(self.session.closed)

    def test_edit_and_delete_commands(self):
        """Контакти й нотатки можна оновлювати та видаляти через команди."""
        for command in (
            'add-contact Лада phone="+38 050-123-45-67" address="вул. Зоряна 2"',
            'edit-contact Лада name "Лада Зоряна"',
            'edit-contact "Лада Зоряна" address "вул. Тиха 3"',
            'add-note План "Прочитати тему" курс',
            'edit-note План "Підготувати виступ"',
            "set-tags План підготовка курс",
            "delete-tag План курс",
        ):
            with self.subTest(command=command):
                self.assertNotIn("Помилка:", self.session.execute(command))
        self.assertIn("Тиха", self.session.execute("find-contact зоряна"))
        self.assertIn("0501234567", self.session.execute('find-contact "+38 050-123"'))
        self.assertIn("Підготувати", self.session.execute("find-note виступ"))
        self.assertIn("План", self.session.execute("find-tag підготовка"))
        self.assertIn("видалено", self.session.execute("delete-note План"))
        self.assertIn("видалено", self.session.execute('delete-contact "Лада Зоряна"'))
        self.assertEqual(self.session.execute("all-notes"), "Записів не знайдено.")
        self.assertEqual(self.session.execute("all-contacts"), "Записів не знайдено.")

    def test_save_only_after_real_change(self):
        """Збереження викликається лише після справжньої зміни даних."""
        storage = Mock()
        session = Session(AddressBook(), NoteBook(), storage)

        self.assertIn("додано", session.execute("add-contact Лада"))
        storage.save.assert_called_once()

        session.execute("all-contacts")
        reply = session.execute("edit-contact Лада email помилка")

        self.assertIn("Помилка", reply)
        storage.save.assert_called_once()
        self.assertIn("Лада", session.execute("all-contacts"))