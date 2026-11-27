"""Запуск текстового інтерфейсу з коректним завершенням сеансу."""

import sys
from pathlib import Path

if __package__:
    from .commands import Session, help_text
    from .storage import Storage, data_directory, session_lock
    from .terminal import colors_enabled, guided_input, paint, prompt, save_history, setup_line_editing
else:
    # Прямий запуск python main.py має знайти той самий пакет, що й python -m assistant.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from assistant.commands import Session, help_text
    from assistant.storage import Storage, data_directory, session_lock
    from assistant.terminal import colors_enabled, guided_input, paint, prompt, save_history, setup_line_editing

PROMPT = "Помічник> "
KEYS_HINT = "Tab доповнює команди й імена · ↑ ↓ — попередні команди · Ctrl+C скасовує введення"


def main():
    """Завантажити книги, вести діалог і зберегти остаточний стан."""
    directory = data_directory()
    store = Storage(directory)
    history = directory / ".history"
    try:
        with session_lock(directory):
            contacts, notes, warning = store.load()
            session = Session(contacts, notes, store)
            interactive = sys.stdin.isatty()
            color = interactive and colors_enabled(sys.stdout)
            if warning:
                print(paint(warning, color))
            print(paint(help_text(), color))
            editor = setup_line_editing(lambda: session, history) if interactive else None
            if editor is not None:
                print(paint(f"  {KEYS_HINT}", color))
            ask = guided_input(editor) if interactive else None
            invite = prompt(PROMPT, color, editor)
            interrupted = False  # другий Ctrl+C поспіль у запрошенні закриває помічник
            while not session.closed:
                try:
                    line = input(invite if interactive else "")
                except EOFError:
                    if interactive:
                        print()
                    break
                except KeyboardInterrupt:
                    if not interactive or interrupted:
                        print()
                        break
                    interrupted = True
                    print()
                    print(paint("Скасовано. Ще раз Ctrl+C або exit — вихід.", color))
                    continue
                interrupted = False
                try:
                    reply = session.execute(line, ask=ask)
                except EOFError:
                    # Кінець вводу під час заповнення контакту.
                    break
                except KeyboardInterrupt:
                    # Переривання могло статися одразу після заміни файла на диску.
                    contacts, notes, _ = store.load()
                    session = Session(contacts, notes, store)
                    if not interactive:
                        break
                    print()
                    print(paint("Скасовано.", color))
                    continue
                if reply:
                    print(paint(reply, color))
            store.save(session.actions.contacts, session.actions.notes)
            save_history(editor, history)
            print("До побачення!")
    except OSError as error:
        print(f"Не вдалося відкрити або зберегти дані: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Сеанс перервано.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
