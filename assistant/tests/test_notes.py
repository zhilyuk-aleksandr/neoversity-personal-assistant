"""Перевірки нотаток, тегів, пошуку та групування."""

import unittest

from assistant.fields import InputError
from assistant.notes import Note, NoteBook


class NoteTests(unittest.TestCase):
    """Нотатки, редагування, теги та їх групування."""

    def setUp(self):
        """Створити дві вигадані нотатки."""
        self.notes = NoteBook()
        self.notes.add(Note("План", "Прочитати розділ", ["Курс", "Дім"]))
        self.notes.add(Note("Ідея", "Обрати тему"))

    def test_text_and_tag_search(self):
        """Пошук тексту частковий, тег має збігатися повністю."""
        self.assertEqual(self.notes.find("РОЗД")[0].title, "План")
        self.assertEqual(self.notes.find("  ІДЕ  ")[0].title, "Ідея")
        self.assertEqual(self.notes.by_tag("  куРс  ")[0].title, "План")
        self.assertFalse(self.notes.by_tag("кур"))

    def test_modify_delete(self):
        """Текст і теги можна змінювати та видаляти."""
        note = self.notes.get_note("ПЛАН")
        note.edit("Підготувати демо")
        note.add_tag("Захист")
        note.remove_tag("дім")
        self.assertEqual(note.tags, ["курс", "захист"])
        note.set_tags(["Демо", "демо"])
        self.assertEqual(note.tags, ["демо"])
        self.assertEqual(self.notes.find("демо"), [note])
        self.notes.remove("план")
        self.assertFalse(self.notes.find("демо"))

    def test_groups(self):
        """Групи впорядковані, а нотатки без тегів ідуть останніми."""
        self.assertEqual(
            [tag for tag, _ in self.notes.groups()], ["дім", "курс", None]
        )
        self.assertEqual(self.notes.groups()[-1][1][0].title, "Ідея")

    def test_invalid_note(self):
        """Порожні поля й дублікати назв відхиляються."""
        for title, body, tags in (
            ("", "текст", []),
            ("Тема", " ", []),
            ("Тема", "текст", [" "]),
        ):
            with self.subTest(title=title), self.assertRaises(InputError):
                Note(title, body, tags)
        with self.assertRaises(InputError):
            self.notes.add(Note("пЛаН", "інший текст"))

    def test_invalid_tag_replacement_preserves_existing_tags(self):
        """Невдала заміна тегів зберігає весь попередній список."""
        note = self.notes.get_note("План")
        original_tags = note.tags.copy()

        with self.assertRaises(InputError):
            note.set_tags(["новий", " "])

        self.assertEqual(note.tags, original_tags)
