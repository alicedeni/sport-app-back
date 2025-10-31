# Sport App Backend

Backend API для спортивного приложения на Flask.

## Установка

1. Клонируйте репозиторий:

```bash
git clone https://github.com/alicedeni/sport-app-back.git
cd sport-app-back
```

2. Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

3. Настройте переменные окружения:

```bash
copy env.example .env  # Windows
# cp env.example .env  # Linux/Mac
```

Отредактируйте `.env` файл и укажите:

- `SECRET_KEY` - секретный ключ Flask
- `DB_PASSWORD` - пароль от PostgreSQL
- `AWS_ACCESS_KEY_ID` и `AWS_SECRET_ACCESS_KEY` - для загрузки файлов

4. Создайте базу данных PostgreSQL:

```bash
psql -U postgres
CREATE DATABASE sport_app_db;
\q
```

5. Инициализируйте таблицы:

```bash
python init_db.py
```

6. Запустите приложение:

```bash
python app.py
```

Приложение будет доступно по адресу: http://localhost:5000

## API Endpoints

- `/auth/*` - Аутентификация
- `/users/*` - Пользователи
- `/posts/*` - Посты
- `/comments/*` - Комментарии
- `/challenges/*` - Челленджи
- `/admin/*` - Админ панель

## Технологии

- Flask 3.0
- PostgreSQL
- SQLAlchemy 2.0
- JWT аутентификация
- Yandex Object Storage (S3)
