FROM python:3.11-slim AS base

RUN apt -y update
RUN apt install -y curl

########ENVIRONMENT SETTINGS########
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV POETRY_VERSION=2.0.0

# Set the working directory in the container
WORKDIR /src/service

# Copy the shared package so path deps resolve during poetry lock
COPY shared/gatepass_auth /shared/gatepass_auth/

# Copy the pyproject.toml and lock file to the working directory
COPY services/revenue_service/pyproject.toml services/revenue_service/poetry.lock services/revenue_service/README.md /src/service/

RUN pip install poetry==${POETRY_VERSION} && poetry config virtualenvs.create false
RUN poetry lock --no-cache --no-interaction

# Install the dependencies
RUN poetry install --no-root --no-interaction

# Copy the application code
ENV POETRY_PLUGIN_DOTENV_LOCATION=.env
COPY services/revenue_service/app /src/service/app

# App stage
FROM base AS app
EXPOSE 9037
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9037"]

# App is the default stage
FROM app
