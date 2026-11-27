"""Редагування рядка в терміналі: стрілки, історія команд і доповнення Tab.

Працює через стандартний модуль readline (macOS, Linux). На Windows його немає,
але консоль Windows і так уміє стрілки та історію,
тож помічник просто працює без Tab.
"""

import os
import re
import shlex

from .commands import COMMANDS
from .suggest import ALIASES

# Перший аргумент цих команд — ім'я контакту, заголовок нотатки або тег.
CONTACT_FIRST = {
    "edit-contact",
    "delete-contact",
    "find-contact",
    "add-phone",
    "edit-phone",
    "delete-phone",
}
NOTE_FIRST = {
    "edit-note",
    "delete-note",
    "find-note",
    "set-tags",
    "add-tag",
    "delete-tag",
}
TAG_FIRST = {"find-tag"}
HISTORY_LENGTH = 500


def _quoted(value, force):
    """Повернути один аргумент, який shlex відновить без зміни назви."""
    if force or any(
        char.isspace() or char in ("'", '"', "\\") for char in value
    ):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}" '
    return value + " "


def completions(line, text, session):
    """Варіанти для слова text, якщо перед курсором стоїть рядок line."""
    head = line[: len(line) - len(text)]
    try:
        words = shlex.split(head)
    except ValueError:
        words = head.split()
    if not words:
        names = [*COMMANDS, *ALIASES]
        return [
            f"{name} " for name in names if name.startswith(text.casefold())
        ]
    if len(words) != 1:
        return []
    command = ALIASES.get(words[0].casefold(), words[0].casefold())
    actions = session.actions
    if command == "help":
        pool = list(COMMANDS)
    elif command in CONTACT_FIRST:
        pool = [str(record.name) for record in actions.contacts.values()]
    elif command in NOTE_FIRST:
        pool = [note.title for note in actions.notes.values()]
    elif command in TAG_FIRST:
        pool = sorted(
            {tag for note in actions.notes.values() for tag in note.tags}
        )
    else:
        return []
    quote = text.startswith('"')
    needle = text.lstrip('"').casefold()
    return [
        _quoted(item, quote)
        for item in pool
        if item.casefold().startswith(needle)
    ]


def setup_line_editing(current_session, history_path):
    """Увімкнути стрілки, історію та Tab. Повертає readline або None,
    якщо модуля немає.
    """
    try:
        import readline
    except ImportError:
        return None

    matches = []

    def complete(text, state):
        if state == 0:
            line = readline.get_line_buffer()[: readline.get_endidx()]
            matches[:] = completions(line, text, current_session())
        return matches[state] if state < len(matches) else None

    readline.set_completer_delims(" \t\n")
    readline.set_completer(complete)
    if "libedit" in (readline.__doc__ or ""):
        readline.parse_and_bind(
            "bind ^I rl_complete"
        )  # системний Python на macOS
    else:
        readline.parse_and_bind("tab: complete")
    readline.set_history_length(HISTORY_LENGTH)
    try:
        readline.read_history_file(history_path)
    except OSError:
        pass  # першого запуску файлу ще немає
    return readline


def guided_input(readline):
    """input() для покрокових питань: відповіді не засмічують історію
    команд.
    """

    def ask(prompt):
        value = input(prompt)
        if readline is not None and value.strip():
            length = readline.get_current_history_length()
            if length and readline.get_history_item(length) == value:
                readline.remove_history_item(length - 1)
        return value
    return ask


def save_history(readline, history_path):
    """Зберегти історію для наступного запуску. Невдача не заважає виходу."""
    if readline is None:
        return
    try:
        readline.write_history_file(history_path)
    except OSError:
        pass


# Кольори термінала
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
RED, GREEN, YELLOW, CYAN = "\033[31m", "\033[32m", "\033[33m", "\033[36m"
DONE = re.compile(r"(додано|оновлено|видалено)\.$")
LABEL = re.compile(r"^(  [^:\n]{1,30}:)( .*)$")
MENU_ROW = re.compile(
    r"^(  )([a-z-]+)(\s{2,}.*)$"
)  # рядок меню: назва команди й опис


def colors_enabled(stream):
    """Кольори лише в справжньому терміналі; NO_COLOR або TERM=dumb їх
    вимикають.
    """
    if (
        os.environ.get("NO_COLOR") is not None
        or os.environ.get("TERM") == "dumb"
    ):
        return False
    if not stream.isatty():
        return False
    if os.name == "nt":
        os.system("")  # вмикає ANSI-послідовності в консолі Windows
    return True


def paint(text, enabled):
    """Помилки червоним, успіх зеленим, підказки жовтим, заголовки
    жирним, підписи полів тьмяно.
    """
    if not enabled or not text:
        return text
    if text.startswith(("Помилка:", "Не вдалося")):
        return f"{RED}{text}{RESET}"
    if text.startswith(
        ("Невідома команда", "Скасовано", "Файл даних пошкоджено", "Увага")
    ):
        return f"{YELLOW}{text}{RESET}"
    if "\n" not in text and DONE.search(text):
        return f"{GREEN}{text}{RESET}"
    source = text.split("\n")
    lines = []
    for index, line in enumerate(source):
        following = source[index + 1] if index + 1 < len(source) else ""
        label = LABEL.match(line)
        row = MENU_ROW.match(line)
        if row:
            line = f"{row[1]}{CYAN}{row[2]}{RESET}{row[3]}"
        elif label:
            line = f"{DIM}{label[1]}{RESET}{label[2]}"
        elif line.startswith("─") or line.lstrip().startswith(
            (
                "Контактів:",
                "Опис і приклади",
                "Назви з пробілами",
                "Tab доповнює",
            )
        ):
            line = f"{DIM}{line}{RESET}"
        elif line and not line.startswith(" ") and (
            following.startswith(("  ", "─")) or line == "Команди помічника"
        ):
            line = (
                f"{BOLD}{line}{RESET}"  # заголовок картки, розділу чи таблиці
            )
        lines.append(line)
    return "\n".join(lines)


def prompt(text, enabled, readline):
    """Кольорове запрошення. Для readline кольорові коди беремо в
    \\001…\\002, щоб не збити курсор.
    """
    if not enabled:
        return text
    start, end = (("\001", "\002") if readline is not None else ("", ""))
    return f"{start}{BOLD}{CYAN}{end}{text.rstrip()}{start}{RESET}{end} "
