@echo off
rem Запуск помічника подвійним кліком у Windows. Потрібен Python 3.12+ з python.org.
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
py -3 -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul && (
    py -3 -B assistant\main.py
    goto :end
)
python -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul && (
    python -B assistant\main.py
    goto :end
)
echo Для запуску помічника потрібен Python 3.12 або новіший: https://www.python.org/downloads/
:end
pause
