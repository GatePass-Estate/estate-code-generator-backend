FROM python:3.11-slim AS base

RUN apt -y update
RUN apt install -y curl

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV POETRY_VERSION=2.0.0

WORKDIR /src/service

# Copy the shared package so path deps resolve during poetry lock
COPY shared/gatepass_auth /shared/gatepass_auth/

COPY services/ai_service/pyproject.toml services/ai_service/poetry.lock services/ai_service/README.md /src/service/

RUN pip install poetry==${POETRY_VERSION} && poetry config virtualenvs.create false
RUN poetry lock --no-cache --no-interaction

RUN poetry install --no-root --no-interaction

ENV POETRY_PLUGIN_DOTENV_LOCATION=.env
COPY services/ai_service/app /src/service/app

FROM base AS app
EXPOSE 9036
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9036"]

FROM app
