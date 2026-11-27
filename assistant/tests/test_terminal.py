"""Перевірки зручності терміналу: підказки, доповнення Tab і Ctrl+C."""

import io
import os
import shlex
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from assistant.address_book import AddressBook
from assistant.commands import COMMANDS, Session
from assistant.main import main
from assistant.notes import NoteBook
from assistant.storage import Storage
from assistant.suggest import candidates, suggest
from assistant.terminal import completions


class SuggestTests(unittest.TestCase):
    """Описка веде до потрібної команди, а не до випадкової."""

    def test_prefix_and_parts(self):
        """Початок назви й частина після дефіса важать більше за
        загальну схожість.
        """
        self.assertEqual(candidates("find-c", COMMANDS), ["find-contact"])
        self.assertEqual(
            candidates("find", COMMANDS),
            ["find-contact", "find-note", "find-tag"],
        )
        self.assertEqual(
            candidates("fnd", COMMANDS)[:3],
            ["find-contact", "find-note", "find-tag"],
        )
        self.assertEqual(candidates("contacts", COMMANDS), ["all-contacts"])
        self.assertEqual(candidates("ad-contact", COMMANDS)[0], "add-contact")
        self.assertEqual(candidates("жжжжж", COMMANDS), [])

    def test_ukrainian_layout(self):
        """Команда, набрана в українській розкладці, впізнається."""
        self.assertIn("«add-contact»", suggest("фвв-сщтефсе", COMMANDS))
        self.assertIn("розкладк", suggest("фвв-сщтефсе", COMMANDS))

    def test_messages(self):
        """Одна підказка — питання, кілька — перелік, жодної — help."""
        self.assertIn("«find-contact»?", suggest("find-c", COMMANDS))
        self.assertIn("«find-note»", suggest("find", COMMANDS))
        self.assertIn("help", suggest("жжжжж", COMMANDS))


class CompletionTests(unittest.TestCase):
    """Tab доповнює команди, імена контактів, заголовки нотаток і теги."""

    def setUp(self):
        self.session = Session(AddressBook(), NoteBook(), Mock())
        self.session.execute('add "Лада Зоряна"')
        self.session.execute("add Олег")
        self.session.execute('add-note "План демо" "Слайди" навчання')

    def test_command_names(self):
        self.assertEqual(
            completions("find-c", "find-c", self.session), ["find-contact "]
        )
        self.assertIn("add-contact ", completions("", "", self.session))
        self.assertEqual(
            completions("help bi", "bi", self.session), ["birthdays "]
        )

    def test_names_titles_and_tags(self):
        """Назва з пробілом береться в лапки, щоб команда одразу працювала."""
        self.assertEqual(
            completions("delete-contact ла", "ла", self.session),
            ['"Лада Зоряна" '],
        )
        self.assertEqual(
            completions('edit-contact "Ла', '"Ла', self.session),
            ['"Лада Зоряна" '],
        )
        self.assertEqual(
            completions("add-phone О", "О", self.session), ["Олег "]
        )
        self.assertEqual(
            completions("edit-note пл", "пл", self.session), ['"План демо" ']
        )
        self.assertEqual(
            completions("find-tag на", "на", self.session), ["навчання "]
        )

    def test_no_guessing_after_first_argument(self):
        """Далі йдуть вільні значення, тож доповнення мовчить."""
        self.assertEqual(
            completions("add-phone Олег 05", "05", self.session), []
        )
        self.assertEqual(completions("exit ", "", self.session), [])

    def test_completed_name_round_trips_through_the_command_parser(self):
        """Доповнення для апострофів, лапок і зворотної скісної риски
        знаходить точний запис.
        """
        for name in ("Мар'яна", 'Софія "Сонце"', r"Ірина\Олена"):
            with self.subTest(name=name):
                self.assertIn(
                    "додано", self.session.execute("add " + shlex.quote(name))
                )
                prefix = name[:3]
                line = "find-contact " + prefix
                chosen, = completions(line, prefix, self.session)
                self.assertEqual(shlex.split(chosen), [name])
                self.assertIn(
                    name, self.session.execute("find-contact " + chosen)
                )


class InterruptTests(unittest.TestCase):
    """Ctrl+C скасовує поточне введення, а не закриває помічник."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)

    def run_main(self, inputs):
        out = io.StringIO()
        tty = Mock(**{"isatty.return_value": True})
        with (
            patch.dict(os.environ, ASSISTANT_DATA_DIR=str(self.directory)),
            patch.object(sys, "stdin", tty),
            patch("builtins.input", side_effect=inputs),
            redirect_stdout(out),
        ):
            self.assertEqual(main(), 0)
        return out.getvalue()

    def test_ctrl_c_cancels_and_double_ctrl_c_exits(self):
        output = self.run_main(
            [
                "add-note",
                "Чернетка",
                KeyboardInterrupt(),  # посеред покрокового введення
                "add-note План Текст",
                KeyboardInterrupt(),  # один Ctrl+C у запрошенні
                "all-notes",
                KeyboardInterrupt(),
                KeyboardInterrupt(),
            ]
        )
        notes = Storage(self.directory).load()[1]
        self.assertEqual(notes.get_note("План").text, "Текст")
        self.assertNotIn("чернетка", notes)
        self.assertIn("Скасовано", output)
        self.assertIn(
            "Текст", output
        )  # all-notes виконано після першого Ctrl+C
        self.assertIn("До побачення!", output)


if __name__ == "__main__":
    unittest.main()
