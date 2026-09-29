# Installation

Validated with Python 3.12.14 and Django 5.2.17 in `.venv-codex312`. Create the environment, install `requirements.txt`, set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and `DJANGO_ALLOWED_HOSTS`, then run `manage.py migrate`, `check`, and `test`. SQLite is the offline development fallback. Set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` for PostgreSQL.
