FROM python:3.14-slim

WORKDIR /app/server

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY src/server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/server/ .

ENV PYTHONPATH=/app/server
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
