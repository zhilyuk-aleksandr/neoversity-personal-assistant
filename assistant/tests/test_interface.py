"""Перевірки вигляду відповідей: довідка, підтвердження, таблиця, дні
народження, кольори.
"""

import unittest
from datetime import date, timedelta
from unittest.mock import Mock

from assistant.address_book import AddressBook
from assistant.commands import (
    COMMAND_EXAMPLES,
    COMMANDS,
    DESCRIPTIONS,
    Session,
    help_text,
)
from assistant.notes import NoteBook
from assistant.terminal import paint, prompt
from assistant.view import birthday_lines, contact_table, plural


def answers(*values):
    """Відповіді користувача на покрокові питання по черзі."""
    queue = iter(values)
    return lambda _prompt: next(queue)


class HelpTests(unittest.TestCase):
    def test_grouped_menu_with_descriptions(self):
        menu = help_text()
        self.assertEqual(menu.count("Команди помічника"), 1)
        for section in ("Контакти", "Нотатки", "Інше"):
            self.assertIn(f"\n{section}\n", menu)
        self.assertIn("дні народження через N днів", menu)

    def test_every_command_has_description_and_example(self):
        self.assertEqual(set(DESCRIPTIONS), set(COMMANDS))
        self.assertEqual(set(COMMAND_EXAMPLES), set(COMMANDS))
        self.assertIn("--within", help_text("birthdays"))
        self.assertIn("протягом", help_text("birthdays"))
        self.assertIn(
            "через N днів", help_text("birthdays")
        )  # регістр опису не ламається


class DialogTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(AddressBook(), NoteBook(), Mock())
        self.session.execute('add "Лада Зоряна" 0501234567')
        self.session.execute('add-note План "Слайди" демо')

    def test_delete_asks_for_confirmation(self):
        reply = self.session.execute(
            'delete-contact "Лада Зоряна"', ask=answers("")
        )
        self.assertIn("нічого не видалено", reply)
        self.assertIn("Лада", self.session.execute("all-contacts"))
        self.assertIn(
            "видалено",
            self.session.execute(
                'delete-contact "лада зоряна"', ask=answers("т")
            ),
        )
        self.assertIn("порожня", self.session.execute("all-contacts"))
        self.assertIn(
            "нічого не видалено",
            self.session.execute("delete-note План", ask=answers("ні")),
        )
        self.assertIn(
            "видалено",
            self.session.execute("delete-note План", ask=answers("так")),
        )

    def test_missing_contact_is_reported_before_confirmation(self):
        reply = self.session.execute("delete-contact Нікого", ask=answers("т"))
        self.assertIn("Помилка:", reply)

    def test_scripts_delete_without_questions(self):
        self.assertIn(
            "видалено", self.session.execute('delete-contact "Лада Зоряна"')
        )

    def test_missing_arguments_are_asked(self):
        self.assertIn(
            "Лада Зоряна",
            self.session.execute("find-contact", ask=answers("лада")),
        )
        self.assertIn(
            "Телефон додано",
            self.session.execute(
                "add-phone", ask=answers("Лада Зоряна", "0507654321")
            ),
        )
        self.assertEqual(
            self.session.execute("find-tag", ask=answers("")), "Скасовано."
        )
        self.assertIn(
            "Помилка:", self.session.execute("find-contact")
        )  # без терміналу — підказка формату

    def test_empty_results_explain_what_to_do(self):
        self.assertIn("«Олег»", self.session.execute("find-contact Олег"))
        self.assertIn("«нічого»", self.session.execute("find-tag нічого"))
        self.assertIn("«нічого»", self.session.execute("find-note нічого"))


class ViewTests(unittest.TestCase):
    def test_plural(self):
        self.assertEqual(
            [
                plural(n, "день", "дні", "днів")
                for n in (1, 2, 5, 11, 21, 22, 112)
            ],
            ["день", "дні", "днів", "днів", "день", "дні", "днів"],
        )

    def test_table_fits_terminal_and_sorts_by_name(self):
        book = AddressBook()
        session = Session(book, NoteBook(), Mock())
        session.execute(
            'add "Олег" 0501234567 '
            'address="Київ, вулиця Дуже Довга Назва 123, квартира 45"'
        )
        session.execute(
            'add "Анна" email=anna@example.com birthday=01.02.2000'
        )
        table = contact_table(session.actions.contacts.values(), width=70)
        lines = table.splitlines()
        self.assertTrue(lines[0].startswith("Ім’я"))
        self.assertTrue(lines[2].startswith("Анна"))
        self.assertTrue(all(len(line) <= 70 for line in lines), table)
        self.assertIn("…", table)
        self.assertIn("Контактів: 2", table)

    def test_birthdays_with_weekday_wait_and_age(self):
        today = date(2026, 11, 25)
        book = AddressBook()
        session = Session(book, NoteBook(), Mock())
        session.execute("add Лада birthday=30.11.2000")
        session.execute("add Олег birthday=26.11.1990")
        book = (
            session.actions.contacts
        )  # після запису сеанс працює з новою копією книги
        exact = birthday_lines(book.birthdays(5, today=today), 5, False, today)
        self.assertIn("Через 5 днів (30.11, понеділок)", exact)
        self.assertIn("Лада — виповнюється 26 років", exact)
        period = birthday_lines(
            book.birthdays(7, within=True, today=today), 7, True, today
        )
        self.assertIn("завтра", period)
        self.assertIn("виповнюється 36 років", period)
        self.assertIn("немає", birthday_lines([], 3, False, today))

    def test_birthdays_command_uses_real_today(self):
        session = Session(AddressBook(), NoteBook(), Mock())
        soon = date.today() + timedelta(days=3)
        session.execute(f"add Лада birthday={soon:%d.%m}.2000")
        self.assertIn("Через 3 дні", session.execute("birthdays 3"))


class ColorTests(unittest.TestCase):
    def test_colors_only_when_enabled(self):
        self.assertEqual(paint("Помилка: x", False), "Помилка: x")
        self.assertIn("\033[31m", paint("Помилка: x", True))
        self.assertIn("\033[32m", paint("Контакт «Лада» додано.", True))
        self.assertIn("\033[33m", paint("Невідома команда «x».", True))
        self.assertIn("\033[2m", paint("Лада\n  Телефони: 0501234567", True))

    def test_only_headers_are_bold(self):
        table = paint(
            "Ім’я  Email\n────  ─────\nЛада  —\nКонтактів: 1", True
        ).splitlines()
        self.assertTrue(table[0].startswith("\033[1m"))
        self.assertFalse(table[2].startswith("\033["))
        card = paint("Лада\n  Телефони: 0501234567", True).splitlines()
        self.assertTrue(card[0].startswith("\033[1m"))
        self.assertEqual(
            paint("демо: План\nкурс: План", True), "демо: План\nкурс: План"
        )

    def test_prompt_wraps_codes_for_readline(self):
        self.assertEqual(prompt("Помічник> ", False, None), "Помічник> ")
        self.assertIn("\001", prompt("Помічник> ", True, object()))
        self.assertNotIn("\001", prompt("Помічник> ", True, None))


if __name__ == "__main__":
    unittest.main()
