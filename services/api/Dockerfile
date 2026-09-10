FROM python:3.11-slim

# System deps for bcrypt and asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model at build time.
# Non-fatal by design: if the download fails (offline/air-gapped build), the
# image still builds and the API degrades to regex-only entity extraction at
# runtime (see app/nlp/spacy_model.py). Known deployment dependency — README#"Known Limitations".
ARG SPACY_MODEL=en_core_web_sm
RUN python -m spacy download ${SPACY_MODEL} \
    || echo "WARNING: spaCy model '${SPACY_MODEL}' could not be downloaded — extraction will run in regex-only mode"

COPY . .

# Run as non-root
RUN useradd --create-home appuser \
    && mkdir -p /uploads \
    && chown -R appuser:appuser /uploads
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
