FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY ui/static/ ./ui/static/
COPY docs/seed/ ./docs/seed/

ENV PYTHONPATH=src
ENV EPAYROLL_AUTH_MODE=stub

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "epayroll.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
