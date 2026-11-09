# Image du bot de copy trading eToro
FROM python:3.12-slim

# poppler-utils (pdftotext) : nécessaire pour lire les déclarations du Congrès
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=UTC
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY vendor ./vendor
COPY config.yaml .

# Le bot tourne sans droits administrateur
RUN useradd --create-home bot && mkdir -p /app/data && chown -R bot /app
USER bot

# Par défaut : la boucle 24h/24. Ajoutez --dry-run dans docker-compose.yml pour simuler.
ENTRYPOINT ["python", "-m", "bot.main"]
