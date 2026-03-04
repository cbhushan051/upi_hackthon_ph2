FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY npci/requirements.txt .
COPY requirements_phase2.txt ./phase2_requirements.txt
RUN pip install --no-cache-dir --timeout 180 --retries 5 -r requirements.txt && \
    pip install --no-cache-dir --timeout 180 --retries 5 -r phase2_requirements.txt

# Phase 2: Copy agent infrastructure
COPY agents/ ./agents/
COPY manifest.py a2a_protocol.py code_updater.py llm.py ./

COPY npci/app.py .
COPY common/schemas/upi_req_valadd.xsd common/schemas/upi_resp_valadd.xsd common/schemas/upi_pay_request.xsd common/schemas/upi_resppay_response.xsd ./schemas/

ENV PORT=5000
EXPOSE 5000

CMD ["python", "app.py"]

