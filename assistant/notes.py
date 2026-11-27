"""Нотатки з пошуком та групуванням за тегами."""

from collections import UserDict

from .fields import InputError, required_text


def clean_tag(value):
    """Повернути непорожній тег у спільному для пошуку регістрі."""
    return required_text(value, "тег").casefold()


class Note:
    """Текстова нотатка з унікальним заголовком і списком тегів."""

    def __init__(self, title, text, tags=()):
        self.title = required_text(title, "заголовок")
        self.edit(text)
        self.set_tags(tags)

    def edit(self, text):
        """Замінити текст нотатки."""
        self.text = required_text(text, "текст нотатки")

    def set_tags(self, tags):
        """Замінити весь список тегів, зберігши порядок унікальних значень."""
        if not isinstance(tags, (list, tuple)):
            raise InputError("Теги мають бути списком.")
        self.tags = list(dict.fromkeys(clean_tag(tag) for tag in tags))

    def add_tag(self, value):
        """Додати один тег."""
        tag = clean_tag(value)
        if tag in self.tags:
            raise InputError("Такий тег уже є в нотатки.")
        self.tags.append(tag)

    def remove_tag(self, value):
        """Видалити тег з нотатки."""
        tag = clean_tag(value)
        if tag not in self.tags:
            raise InputError("У нотатки немає такого тегу.")
        self.tags.remove(tag)

    def to_dict(self):
        """Підготувати нотатку до запису у JSON."""
        return {"title": self.title, "text": self.text, "tags": self.tags.copy()}

    def __str__(self):
        return f"{self.title}\n  {self.text}\n  Теги: {', '.join(self.tags) or '—'}"


class NoteBook(UserDict):
    """Колекція нотаток, доступних за заголовком."""

    def add(self, note):
        """Додати нотатку з унікальним заголовком."""
        key = note.title.casefold()
        if key in self.data:
            raise InputError("Нотатка з таким заголовком уже є.")
        self.data[key] = note

    def get_note(self, title):
        """Повернути нотатку за точним заголовком."""
        key = required_text(title, "заголовок").casefold()
        if key not in self.data:
            raise InputError("Нотатку з таким заголовком не знайдено.")
        return self.data[key]

    def remove(self, title):
        """Видалити нотатку за заголовком."""
        note = self.get_note(title)
        del self.data[note.title.casefold()]

    def find(self, query):
        """Шукати фрагмент тексту або заголовка."""
        query = required_text(query, "запит").casefold()
        return [
            note for note in self.values()
            if query in note.text.casefold() or query in note.title.casefold()
        ]

    def by_tag(self, value):
        """Повернути нотатки з указаним тегом."""
        tag = clean_tag(value)
        return [note for note in self.values() if tag in note.tags]

    def groups(self):
        """Згрупувати за тегами, а нотатки без тегів показати окремо в кінці."""
        groups = {}
        untagged = []
        for note in sorted(self.values(), key=lambda item: item.title.casefold()):
            for tag in note.tags:
                groups.setdefault(tag, []).append(note)
            if not note.tags:
                untagged.append(note)
        result = sorted(groups.items())
        if untagged:
            result.append((None, untagged))
        return result
