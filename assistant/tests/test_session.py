"""Перевірки диска, діалогу й повторного запуску реального процесу."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from assistant.commands import Session
from assistant.main import main
from assistant.storage import Storage, session_lock

PROJECT = Path(__file__).resolve().parents[2]


class SessionTests(unittest.TestCase):
    """Робота з ізольованою текою замість справжніх даних користувача."""

    def setUp(self):
        """Підготувати порожню теку даних та сеанс."""
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)
        self.store = Storage(self.directory)
        contacts, notes, _ = self.store.load()
        self.session = Session(contacts, notes, self.store)

    def test_persists_after_command(self):
        """Новий читач одразу бачить щойно збережені зміни."""
        self.session.execute('add "Лада Зоряна" phone=0501234567')
        self.session.execute('add-note "План" "Підготувати приклади" демо')
        contacts, notes, warning = self.store.load()
        self.assertFalse(warning)
        self.assertEqual(
            str(contacts.get_record("Лада Зоряна").phones[0]), "0501234567"
        )
        self.assertEqual(notes.get_note("План").tags, ["демо"])

    def test_failed_write_is_retryable(self):
        """Помилка диска не змінює книги, команду можна повторити."""
        self.session.execute("add Лада")
        previous = self.store.path.read_bytes()
        with patch(
            "assistant.storage.os.replace", side_effect=OSError("диск")
        ):
            self.assertIn("Не вдалося", self.session.execute("add Зоря"))
        self.assertNotIn("Зоря", self.session.execute("all-contacts"))
        self.assertEqual(previous, self.store.path.read_bytes())
        self.assertEqual(list(self.directory.iterdir()), [self.store.path])
        self.assertIn("додано", self.session.execute("add Зоря"))

    def test_damaged_or_missing_data(self):
        """Пошкоджений оригінал зберігається, порожня тека підтримується."""
        for raw in (
            b"{!",
            b"null",
            b'{"contacts": [12], "notes": []}',
            b"\xff",
            br'{"contacts": [{"name": "\ud800"}], "notes": []}',
        ):
            with self.subTest(raw=raw):
                self.store.path.write_bytes(raw)
                contacts, notes, warning = self.store.load()
                self.assertFalse(contacts)
                self.assertFalse(notes)
                self.assertIn("пошкоджено", warning)
                backups = self.directory.glob("*damaged*")
                self.assertTrue(any(p.read_bytes() == raw for p in backups))
                self.assertFalse(self.store.path.exists())
        self.assertFalse(self.store.load()[2])

    def run_process(self, command_line, input_text):
        """Запустити помічник як зовнішній процес у виділеній теці."""
        env = dict(
            os.environ,
            ASSISTANT_DATA_DIR=str(self.directory),
            PYTHONIOENCODING="utf-8",
        )
        return subprocess.run(
            [sys.executable, "-B", *command_line],
            cwd=PROJECT,
            env=env,
            input=input_text,
            capture_output=True,
            encoding="utf-8",
            timeout=10,
        )

    @unittest.skipUnless(
        sys.platform == "darwin", "Файл запуску призначено для macOS."
    )
    def test_mac_launcher_finds_its_package(self):
        """Файл запуску знаходить пакет, навіть коли Python пропускає
        поточну теку.
        """
        env = dict(
            os.environ,
            ASSISTANT_DATA_DIR=str(self.directory),
            PYTHONSAFEPATH="1",
        )
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [str(PROJECT / "Запустити.command")], cwd=self.directory, env=env,
            input="exit\n", capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Команди помічника", result.stdout)
        self.assertIn("До побачення!", result.stdout)

    @unittest.skipUnless(
        os.name == "nt", "Файл запуску призначено для Windows."
    )
    def test_windows_launcher_finds_its_package(self):
        """Командний файл знаходить пакет з іншої папки й завершує сеанс."""
        env = dict(
            os.environ, ASSISTANT_DATA_DIR=str(self.directory), PYTHONUTF8="1"
        )
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "call", str(PROJECT / "Запустити.bat")],
            cwd=self.directory, env=env, input=b"exit\r\n\r\n",
            capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("До побачення!".encode("utf-8"), result.stdout)
        self.assertTrue(self.store.path.is_file())

    def test_restart_after_corrupt_file_keeps_original_and_new_note(self):
        """Після відновлення другий процес знаходить нотатку, а оригінал
        збережено.
        """
        damaged = b'{"notes":'
        self.store.path.write_bytes(damaged)
        first = self.run_process(
            ["-m", "assistant"], "add-note План Показати демо\nexit\n"
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("Файл даних пошкоджено", first.stdout)
        backups = list(self.directory.glob("assistant-damaged-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), damaged)
        second = self.run_process(["-m", "assistant"], "find-tag демо\nexit\n")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("План", second.stdout)
        self.assertIn("Показати", second.stdout)
        self.assertNotIn("Файл даних пошкоджено", second.stdout)

    def test_two_real_processes(self):
        """Сценарій stdin і другий незалежний запуск читають ті самі дані."""
        scenario = (PROJECT / "assistant/tests/e2e_session.txt").read_text(
            encoding="utf-8"
        )
        first = self.run_process(["assistant/main.py"], scenario)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout.count("Команди помічника"), 1)
        self.assertNotIn("Помилка:", first.stdout)
        self.assertIn("Нотатку «План демо» додано.", first.stdout)
        second = self.run_process(
            ["-m", "assistant"],
            "find-contact\nfind-contact Лада\nfind-tag демо\nhelp\n",
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout.count("Команди помічника"), 2)
        self.assertIn("Помилка:", second.stdout)
        for required in (
            "Лада Зоряна",
            "0501234567",
            "План демо",
            "Показати збереження даних",
        ):
            self.assertIn(required, second.stdout)
        self.assertNotIn("0500000001", second.stdout)
        self.assertTrue(second.stdout.rstrip().endswith("До побачення!"))

    def test_second_process_cannot_overwrite(self):
        """Другий сеанс у тій самій теці не може затерти зміни першого."""
        with session_lock(self.directory):
            second = self.run_process(["-m", "assistant"], "add Інша\n")
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("зайнята", second.stderr)
        self.assertFalse(self.store.path.exists())

    def test_keyboard_interrupt_and_eof(self):
        """Без терміналу (ввід із файла) Ctrl+C та кінець вводу
        закривають сеанс зі збереженням.
        """
        piped = Mock(**{"isatty.return_value": False})
        for position, end in enumerate((KeyboardInterrupt(), EOFError())):
            title = f"План{position}"
            inputs = [f"add-note {title} Текст", end]
            with (
                patch.dict(os.environ, ASSISTANT_DATA_DIR=str(self.directory)),
                patch.object(sys, "stdin", piped),
            ):
                with (
                    patch("builtins.input", side_effect=inputs),
                    redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(main(), 0)
            self.assertEqual(
                self.store.load()[1].get_note(title).text, "Текст"
            )
