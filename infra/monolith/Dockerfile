FROM python:3.11-slim

RUN apt -y update && apt install -y curl nginx supervisor ca-certificates && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV POETRY_VERSION=2.0.0

RUN pip install poetry==${POETRY_VERSION} && poetry config virtualenvs.create false

# ── Copy ALL shared libraries once ──
COPY shared/gatepass_auth        /shared/gatepass_auth/
COPY shared/gatepass_docs        /shared/gatepass_docs/
COPY shared/gatepass_entitlement /shared/gatepass_entitlement/
COPY shared/gatepass_llm         /shared/gatepass_llm/
COPY shared/gatepass_notify      /shared/gatepass_notify/
COPY shared/gatepass_rbac        /shared/gatepass_rbac/
COPY shared/gatepass_scheduler   /shared/gatepass_scheduler/

# ── Install dependencies for each service ──
# Each service gets its own directory under /src/<name>/

# db-service
WORKDIR /src/db-service
COPY services/db-service/pyproject.toml services/db-service/poetry.lock services/db-service/README.md ./
RUN poetry lock --no-cache --no-interaction && poetry install --no-root --no-interaction
COPY services/db-service/app ./app
COPY services/db-service/alembic.ini ./
COPY services/db-service/alembic ./alembic

# cache-service
WORKDIR /src/cache-service
COPY services/cache_service/pyproject.toml services/cache_service/poetry.lock services/cache_service/README.md ./
RUN poetry lock --no-cache --no-interaction && poetry install --no-root --no-interaction
COPY services/cache_service/app ./app

# code-service
WORKDIR /src/code-service
COPY services/code_service/pyproject.toml services/code_service/poetry.lock services/code_service/README.md ./
RUN poetry lock --no-cache --no-interaction && poetry install --no-root --no-interaction
COPY services/code_service/app ./app

# user-profile-service
WORKDIR /src/user-profile-service
COPY services/user_profile_service/pyproject.toml services/user_profile_service/poetry.lock services/user_profile_service/README.md ./
RUN poetry lock --no-cache --no-interaction && poetry install --no-root --no-interaction
COPY services/user_profile_service/app ./app

# revenue-service
WORKDIR /src/revenue-service
COPY services/revenue_service/pyproject.toml services/revenue_service/poetry.lock services/revenue_service/README.md ./
RUN poetry lock --no-cache --no-interaction && poetry install --no-root --no-interaction
COPY services/revenue_service/app ./app

# ai-service
WORKDIR /src/ai-service
COPY services/ai_service/pyproject.toml services/ai_service/poetry.lock services/ai_service/README.md ./
RUN poetry lock --no-cache --no-interaction && poetry install --no-root --no-interaction
COPY services/ai_service/app ./app

# notification-service
WORKDIR /src/notification-service
COPY services/notification_service/pyproject.toml services/notification_service/poetry.lock services/notification_service/README.md ./
RUN poetry lock --no-cache --no-interaction && poetry install --no-root --no-interaction
COPY services/notification_service/app ./app

# ── Config files ──
COPY infra/monolith/nginx.conf /etc/nginx/conf.d/default.conf
COPY infra/monolith/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY infra/monolith/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Remove default nginx site
RUN rm -f /etc/nginx/sites-enabled/default

EXPOSE 8080

CMD ["/entrypoint.sh"]
