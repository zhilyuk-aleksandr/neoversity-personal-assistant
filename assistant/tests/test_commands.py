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

    def test_short_and_named_contact_fields(self):
        """Короткий запис і обидва написання іменованих полів можна поєднувати."""
        reply = self.session.execute(
            'add Лада +380501234567 Київ email user@example.com birthday=15.04.1995'
        )
        self.assertIn("додано", reply)
        card = self.session.execute("find-contact Лада")
        for value in ("0501234567", "Київ", "user@example.com", "15.04.1995"):
            self.assertIn(value, card)
        reply = self.session.execute("add Тест 123 Київ")
        self.assertIn("10 цифр", reply)
        self.assertEqual(len(self.store.saved), 1)

    def test_edit_multiple_fields_and_commas(self):
        """Коми між полями необов’язкові, а коми в адресі зберігаються."""
        self.session.execute('add "Олена Демо"')
        reply = self.session.execute(
            'edit-contact "Олена Демо" address "Київ, вул. Сонячна 10" , '
            'email user@example.com,  birthday 15.04.1995'
        )
        self.assertIn("оновлено", reply)
        card = self.session.execute('find-contact "Олена Демо"')
        for value in ("Київ, вул. Сонячна 10", "user@example.com", "15.04.1995"):
            self.assertIn(value, card)
        self.assertEqual(len(self.store.saved), 2)
        reply = self.session.execute(
            'edit-contact "Олена Демо" name="Олена Тест",address="Київ, email центр," email ""'
        )
        self.assertIn("оновлено", reply)
        card = self.session.execute('find-contact "Олена Тест"')
        self.assertIn("Київ, email центр,", card)
        self.assertIn("Email: —", card)

    def test_invalid_batch_keeps_original_contact(self):
        """Помилка будь-якого поля скасовує всі зміни цієї команди."""
        self.session.execute("add Лада phone=0501234567 address=Львів")
        before = self.session.execute("all-contacts")
        for changes in (
            "address=Київ email=хиба",
            "name=Інша birthday=31.02.2000",
            "address=Київ address=Львів",
            "address=Київ невідоме=значення",
            "address=Київ email",
            "address, email=user@example.com",
            "phone=0501234567",
        ):
            with self.subTest(changes=changes):
                self.assertIn("Помилка:", self.session.execute("edit-contact Лада " + changes))
                self.assertEqual(self.session.execute("all-contacts"), before)
                self.assertEqual(len(self.store.saved), 1)

    def test_edit_appends_phone_and_help_shows_examples(self):
        """Додатковий номер зберігається поруч зі старим, а приклади доступні з CLI."""
        self.session.execute("add Лада phone=0501234567")
        self.assertIn("оновлено", self.session.execute("edit-contact Лада phone 0671234567"))
        self.assertIn("0501234567, 0671234567", self.session.execute("all-contacts"))
        self.assertIn("0501234567 Київ", self.session.execute("help add"))
        self.assertIn("email=", self.session.execute("help edit-contact"))

    def test_guided_contact_retries_invalid_fields(self):
        """Діалог перевіряє помилкові поля повторно та зберігає контакт лише раз."""
        answers = iter(("Олена Демо", "123", "0501234567", "Київ, вул. Сонячна 10",
                        "олена@", "user@example.com", ""))
        prompts = []

        def ask(prompt):
            prompts.append(prompt)
            return next(answers)

        self.assertIn("додано", self.session.execute("add", ask=ask))
        self.assertTrue(any("10 цифр" in prompt for prompt in prompts))
        self.assertTrue(any("Перевірте email" in prompt for prompt in prompts))
        self.assertIn("Київ, вул. Сонячна 10", self.session.execute("all-contacts"))
        self.assertEqual(len(self.store.saved), 1)

    def test_guided_edit_skip_and_cancel(self):
        """Enter лишає попереднє значення, а скасування не застосовує жодної зміни."""
        self.session.execute("add Лада 0501234567 Київ")
        for inputs, expected in (
            (("", "", "Львів", "/cancel"), "Скасовано"),
            (("", "", "", "", ""), "Змін не внесено"),
            (("", "", "Одеса", "", ""), "оновлено"),
        ):
            with self.subTest(expected=expected):
                replies = iter(inputs)
                result = self.session.execute("edit-contact Лада", ask=lambda _: next(replies))
                self.assertIn(expected, result)
        self.assertEqual(len(self.store.saved), 2)
        card = self.session.execute("all-contacts")
        self.assertIn("Одеса", card)
        self.assertIn("0501234567", card)

    def test_note_one_line_and_partial_updates(self):
        """Текст і список тегів зберігаються разом, а пропущене поле лишається."""
        run = self.session.execute
        self.assertIn("додано", run('add-note "План демо" "Перша версія" курс демо'))
        self.assertIn("оновлено", run('edit-note "План демо" "Друга версія" команда захист'))
        self.assertNotIn("План демо", run("find-tag курс"))
        self.assertIn("Друга версія", run("find-tag команда"))
        self.assertIn("оновлено", run('edit-note "План демо" text="Текст, з комою"'))
        self.assertIn("Текст, з комою", run("find-tag захист"))
        self.assertIn("оновлено", run('edit-note "План демо" tags="важливе, на потім"'))
        self.assertIn("Текст, з комою", run('find-tag "на потім"'))
        self.assertIn("оновлено", run('edit-note "План демо" tags=""'))
        self.assertIn("Теги: —", run('find-note "План демо"'))
        self.assertEqual(len(self.store.saved), 5)

    def test_note_named_fields_and_literal_text(self):
        """Іменовані поля працюють у різному порядку, а лапки захищають текст."""
        run = self.session.execute
        self.assertIn("додано", run('add-note План tags=Демо,курс, text="Пишу, tags=буквально"'))
        self.assertIn("Пишу, tags=буквально", run("find-tag демо"))
        self.assertIn("оновлено", run('edit-note План "tags=залишити як текст"'))
        self.assertIn("tags=залишити як текст", run("find-tag курс"))
        self.assertIn("додано", run('add-note Інша "Звичайний текст" tags=нове,робота'))
        self.assertIn("Інша", run("find-tag робота"))

    def test_invalid_note_update_is_atomic(self):
        """Помилка у тексті чи тегах залишає попередню нотатку на диску й у книзі."""
        run = self.session.execute
        run("add-note План Текст курс")
        before = run("all-notes")
        for line in (
            'edit-note План tags=нове text=""',
            'edit-note План text="Новий текст" tags=один,,два',
            'edit-note План tags=один tags=два',
            'edit-note План tags=один зайве',
            'edit-note План text=Один text=Два',
            'add-note Інша tags=тег',
            'add-note',
        ):
            with self.subTest(line=line):
                self.assertIn("Помилка:", run(line))
                self.assertEqual(run("all-notes"), before)
                self.assertEqual(len(self.store.saved), 1)

    def test_guided_notes(self):
        """Діалог повторює помилкове поле, приймає звичайний текст і дозволяє скасування."""
        run = self.session.execute
        run("add-note Перша Текст старе")

        def guided(line, *values):
            answers = iter(values)
            return run(line, ask=lambda _: next(answers))

        self.assertIn("додано", guided("add-note", "", "перша", "План дня", "",
                                      'Звірити "план", без лапок навколо', "дім,,курс", "дім, курс"))
        self.assertIn('Звірити "план", без лапок навколо', run("find-tag курс"))
        self.assertIn("Скасовано", guided('edit-note "План дня"', "Чернетка", "/cancel"))
        self.assertIn("Змін не внесено", guided('edit-note "План дня"', "", ""))
        self.assertIn("оновлено", guided("edit-note", "План дня", "", "/clear"))
        card = run('find-note "План дня"')
        self.assertIn('Звірити "план"', card)
        self.assertIn("Теги: —", card)
        self.assertIn("Скасовано", guided("add-note", "Скасована", "/cancel"))
        self.assertIn("додано", guided('add-note "Без тегів"', "Лише текст", ""))
        self.assertEqual(len(self.store.saved), 4)
        self.assertIn("tags=", run("help edit-note"))

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
        self.assertIn("Нотаток ще немає", self.session.execute("all-notes"))
        self.assertIn("Книга контактів порожня", self.session.execute("all-contacts"))

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
 