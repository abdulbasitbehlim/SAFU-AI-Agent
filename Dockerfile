FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QT_QPA_PLATFORM=offscreen

WORKDIR /app

# Copy only repository files. Personal config/memory are excluded by .dockerignore.
COPY . /app

# The default image is intentionally lightweight. SAFU's package verifier works
# without cloud credentials, a microphone, or a graphical desktop.
CMD ["python", "verify_safu.py"]
