FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --system --uid 10001 --home-dir /app maxbot

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install .

USER maxbot
EXPOSE 8080

FROM base AS test

USER root
COPY tests ./tests
RUN pip install '.[dev]'
USER maxbot

CMD ["pytest", "-q", "-p", "no:cacheprovider"]

FROM base AS runtime

CMD ["sh", "-c", "alembic upgrade head && python -m app.db.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8080"]
