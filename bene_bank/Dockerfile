FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY bene_bank/requirements.txt .
COPY requirements_phase2.txt ./phase2_requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r phase2_requirements.txt

# Phase 2: Copy agent infrastructure
COPY agents/ ./agents/
COPY manifest.py a2a_protocol.py code_updater.py llm.py ./

COPY bene_bank/app.py .
COPY bene_bank/db ./db

ENV PORT=5000
EXPOSE 5000

CMD ["python", "app.py"]
