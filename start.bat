@echo off
REM Batch скрипт для запуска Flask приложения
REM Использование: start.bat

echo ========================================
echo   Sport App Backend - Starting...
echo ========================================
echo.

REM Проверка виртуального окружения
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Виртуальное окружение не найдено!
    echo Создайте его командой: python -m venv venv
    pause
    exit /b 1
)

REM Активация виртуального окружения
echo [INFO] Активация виртуального окружения...
call venv\Scripts\activate.bat

REM Установка переменных окружения
echo [INFO] Настройка окружения...
set FLASK_APP=app.py
set FLASK_ENV=development

REM Проверка .env файла
if not exist ".env" (
    echo [WARNING] Файл .env не найден!
    echo Скопируйте env.example в .env и настройте переменные
    echo.
)

REM Запуск приложения
echo [INFO] Запуск приложения...
echo Откройте http://localhost:5000 в браузере
echo Для остановки нажмите Ctrl+C
echo.
python app.py

pause

