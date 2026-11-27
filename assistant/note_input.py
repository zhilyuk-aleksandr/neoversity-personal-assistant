"""Однорядкове й покрокове введення нотаток у терміналі."""

import re
import shlex
from io import StringIO

from .fields import InputError, required_text
from .notes import clean_tag


# Кома між іменованими полями є роздільником. Лапки й екрановані символи
# захищають буквальний текст, наприклад text="Нагадати, tags=приклад".
FIELD_COMMA = re.compile(
    r'''("(?:\\.|[^"\\])*"|'[^']*'|\\.)|,(?=\s*(?:text|tags)=)''',
    re.IGNORECASE,
)


def tag_list(value):
    """Прочитати теги через кому. Порожній рядок означає порожній список."""
    if value == "":
        return []
    return [clean_tag(tag) for tag in value.split(",")]


def note_arguments(line):
    """Повернути заголовок, текст і теги. None означає пропущене поле."""
    line = FIELD_COMMA.sub(lambda match: match[1] or " ", line)
    source = StringIO(line)
    lexer = shlex.shlex(source, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    next(lexer)  # назва команди
    title = next(lexer)
    text = None
    tags = None
    extra_tags = []
    while True:
        start = source.tell()
        value = lexer.get_token()
        if value is None:
            break
        # У лапках "text=..." і "tags=..." можуть бути текстом чи тегом.
        raw = line[start:source.tell()].lstrip().casefold()
        if raw.startswith("text="):
            if text is not None:
                raise InputError("Поле text повторюється.")
            text = value.partition("=")[2]
        elif raw.startswith("tags="):
            if tags is not None:
                raise InputError("Поле tags повторюється.")
            if extra_tags:
                raise InputError(
                    "Вкажіть теги одним списком tags= "
                    "або окремими аргументами."
                )
            tags = tag_list(value.partition("=")[2])
        elif tags is not None:
            raise InputError(
                'Після tags= додатковий текст вказуйте як text="Новий текст".'
            )
        elif text is None:
            text = value
        else:
            extra_tags.append(value)
    if extra_tags:
        tags = extra_tags
    return title, text, tags


def guided_note(notes, command, args, ask):
    """Запитати поля й повернути їх разом лише після завершення діалогу."""
    creating = command == "add-note"
    intro = "/cancel скасовує введення.\n"
    tag_prompt = "Теги через кому (Enter — без тегів)"
    if not creating:
        intro = (
            "Enter залишає попереднє значення. /cancel скасовує введення.\n"
        )
        tag_prompt = "Теги через кому (/clear — очистити)"
    fields = (
        ("title", "Заголовок"),
        ("text", "Текст нотатки"),
        ("tags", tag_prompt),
    )
    result = []
    initial = args[0] if args else None
    for key, label in fields:
        while True:
            if initial is None:
                value = ask(intro + label + ": ")
                intro = ""
            else:
                value, initial = initial, None
            value = value.strip()
            if value == "/cancel":
                return "Скасовано."
            try:
                if key == "title":
                    value = required_text(value, "заголовок")
                    if creating and value.casefold() in notes:
                        raise InputError("Нотатка з таким заголовком уже є.")
                    if not creating:
                        notes.get_note(value)
                elif not creating and not value:
                    value = None
                elif key == "text":
                    value = required_text(value, "текст нотатки")
                else:
                    value = (
                        []
                        if not creating and value == "/clear"
                        else tag_list(value)
                    )
            except InputError as error:
                intro = f"{error}\n"
                continue
            result.append(value)
            break
    if not creating and result[1:] == [None, None]:
        return "Змін не внесено."
    return result
