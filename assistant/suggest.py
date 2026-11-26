"""Альтернативні назви команд і підказки після описки."""

from difflib import get_close_matches

ALIASES = {"add": "add-contact", "new": "add-contact", "close": "exit"}


def suggest(word, commands):
    """Повернути повідомлення з найближчою назвою команди, якщо вона є."""
    matches = get_close_matches(word, [*commands, *ALIASES], n=1, cutoff=0.6)
    message = f"Невідома команда «{word}»."
    if matches:
        return f"{message} Можливо, ви мали на увазі «{matches[0]}»?"
    return f"{message} Введіть help, щоб переглянути команди."
