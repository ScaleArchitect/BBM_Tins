# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal for Sprint 0. OCR system libs (e.g. tesseract) are
# added in Sprint 6 when the local OCR provider is implemented.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the project then install it (and its dependencies). Source is needed at
# build time because the package is built from pyproject.
COPY . .
RUN pip install --upgrade pip && pip install .

# Non-root runtime user.
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default command runs the API. The worker/scheduler override this in compose:
#   worker:    arq app.worker.WorkerSettings
#   scheduler: arq app.scheduler.SchedulerSettings
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
