FROM python:3.11-slim

WORKDIR /app

COPY payment_ui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY payment_ui/ .

EXPOSE 8089

CMD ["python", "app.py"]

