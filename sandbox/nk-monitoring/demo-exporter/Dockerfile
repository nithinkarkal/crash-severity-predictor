# Tiny image for the demo metrics exporter (NK monitoring sandbox).
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir "prometheus_client>=0.20,<1.0"
COPY exporter.py .

EXPOSE 8010
CMD ["python", "exporter.py"]
