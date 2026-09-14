FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QT_QPA_PLATFORM=offscreen

WORKDIR /app

COPY requirements-ci.txt /app/requirements-ci.txt
RUN python -m pip install --no-cache-dir -r requirements-ci.txt

# Copy only repository files. Personal config/memory are excluded by .dockerignore.
COPY . /app

# Docker is intentionally a headless verification/development target.
CMD ["python", "verify_safu.py"]
