"""Альтернативні назви команд і підказки після описки."""

from difflib import SequenceMatcher

ALIASES = {"add": "add-contact", "new": "add-contact", "close": "exit"}

# Та сама клавіша в українській і англійській розкладці: «фвв» → «add».
LAYOUT = str.maketrans(
    "йцукенгшщзхїфівапролджєячсмитьбю.", "qwertyuiop[]asdfghjkl;'zxcvbnm,./"
)


def similarity(word, name):
    """Схожість зі всією назвою або з її частиною між дефісами («fnd» ≈ «find»)."""
    parts = [name, *name.split("-")]
    return max(SequenceMatcher(None, word, part).ratio() for part in parts)


def candidates(word, commands, limit=3):
    """Повернути до limit найімовірніших команд у порядку довідки."""
    word = word.casefold()
    names = list(commands)
    by_prefix = [name for name in names if name.startswith(word)]
    if by_prefix:
        return by_prefix[:limit]
    inside = [name for name in names if word in name]
    if inside:
        return inside[:limit]
    scored = [(similarity(word, name), index, name) for index, name in enumerate(names)]
    good = sorted((-score, index, name) for score, index, name in scored if score >= 0.6)
    # Явний лідер («ad-contact» → add-contact) — одна підказка замість переліку.
    if len(good) > 1 and -good[0][0] >= 0.8 and good[1][0] - good[0][0] >= 0.1:
        good = good[:1]
    return [name for _, _, name in good[:limit]]


def suggest(word, commands):
    """Повернути повідомлення з найближчими назвами команд, якщо вони є."""
    message = f"Невідома команда «{word}»."
    switched = word.casefold().translate(LAYOUT)
    switched = ALIASES.get(switched, switched)
    if switched != word.casefold() and switched in commands:
        return f"{message} Схоже, увімкнена українська розкладка: ви мали на увазі «{switched}»?"
    matches = candidates(word, commands)
    if len(matches) == 1:
        return f"{message} Можливо, ви мали на увазі «{matches[0]}»?"
    if matches:
        return f"{message} Можливо: " + ", ".join(f"«{name}»" for name in matches) + "."
    return f"{message} Введіть help, щоб переглянути команди."
