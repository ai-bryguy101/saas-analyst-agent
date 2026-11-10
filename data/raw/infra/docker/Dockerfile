FROM python:3.11-slim
# billing-svc. Built by CI; do not build locally with prod creds.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV TZ=UTC
CMD ["gunicorn", "billing.wsgi", "-w", "4", "-b", "0.0.0.0:8000"]
