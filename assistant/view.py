"""Вигляд відповідей у терміналі: таблиця контактів і дні народження
людською мовою.
"""

import shutil
from datetime import date

WEEKDAYS = (
    "понеділок",
    "вівторок",
    "середа",
    "четвер",
    "пʼятниця",
    "субота",
    "неділя",
)


def plural(number, one, few, many):
    """Українська форма слова після числа: 1 день, 2 дні, 5 днів."""
    if number % 10 == 1 and number % 100 != 11:
        return one
    if 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        return few
    return many


def days_word(number):
    """«5 днів», «1 день», «3 дні»."""
    return f"{number} {plural(number, 'день', 'дні', 'днів')}"


def when(day, today):
    """«сьогодні», «завтра» або «через 5 днів»."""
    delta = (day - today).days
    if delta == 0:
        return "сьогодні"
    if delta == 1:
        return "завтра"
    return f"через {days_word(delta)}"


def birthday_lines(matches, days, within, today=None):
    """Заголовок і рядок на кожен контакт: дата, день тижня, скільки
    чекати, вік.
    """
    today = today or date.today()
    if not matches:
        period = (
            f"у найближчі {days_word(days)}"
            if within
            else f"через {days_word(days)}"
        )
        return f"Днів народження {period} немає."
    if within:
        lines = [f"Дні народження в найближчі {days_word(days)}:"]
    else:
        day = matches[0][0]
        lines = [
            f"{when(day, today).capitalize()} "
            f"({day:%d.%m}, {WEEKDAYS[day.weekday()]}):"
        ]
    for day, record in matches:
        age = day.year - record.birthday.date.year
        turns = f"виповнюється {age} {plural(age, 'рік', 'роки', 'років')}"
        if within:
            lines.append(
                f"  {day:%d.%m} {WEEKDAYS[day.weekday()]:<9} · "
                f"{when(day, today):<13} · {record.name} — {turns}"
            )
        else:
            lines.append(f"  {record.name} — {turns}")
    return "\n".join(lines)


def _cut(text, width):
    return text if len(text) <= width else text[: max(width - 1, 1)] + "…"


def _phones_text(phones, width):
    """Номери, що вміщаються в колонку: решту замінює «+N», повний
    список — у картці.
    """
    text = ", ".join(map(str, phones)) or "—"
    if len(text) <= width or len(phones) < 2:
        return text
    for shown in range(len(phones) - 1, 0, -1):
        short = f"{', '.join(map(str, phones[:shown]))} +{len(phones) - shown}"
        if len(short) <= width:
            return short
    return f"{phones[0]} +{len(phones) - 1}"


def contact_table(records, width=None):
    """Усі контакти таблицею, що вміщається в ширину терміналу."""
    records = sorted(records, key=lambda record: str(record.name).casefold())
    if not records:
        return "Книга контактів порожня. Додайте перший контакт: add-contact"
    width = width or shutil.get_terminal_size((100, 24)).columns
    head = ("Ім’я", "Телефони", "Email", "День нар.", "Адреса")
    rows = [
        (
            str(record.name),
            record.phones,
            str(record.email or "—"),
            str(record.birthday or "—"),
            str(record.address or "—"),
        )
        for record in records
    ]
    widths = [
        max(
            len(head[i]),
            *(
                len(_phones_text(row[i], 10**9) if i == 1 else row[i])
                for row in rows
            ),
        )
        for i in range(len(head))
    ]
    phones_min = max(
        len(head[1]), *(len(_phones_text(row[1], 0)) for row in rows)
    )
    gap = 2
    # Спершу стискаємо адресу, потім email, телефони й ім’я.
    for column, minimum in ((4, 8), (2, 10), (1, phones_min), (0, 10)):
        excess = sum(widths) + gap * (len(widths) - 1) - width
        if excess <= 0:
            break
        widths[column] = max(minimum, widths[column] - excess)
    rows = [
        (row[0], _phones_text(row[1], widths[1]), *row[2:]) for row in rows
    ]

    def line(cells):
        return (
            (" " * gap)
            .join(_cut(cell, w).ljust(w) for cell, w in zip(cells, widths))
            .rstrip()
        )

    out = [line(head), (" " * gap).join("─" * w for w in widths)]
    out.extend(line(row) for row in rows)
    out.append(f"Контактів: {len(rows)}")
    return "\n".join(out)
