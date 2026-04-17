FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY medagent ./medagent
COPY data ./data
COPY scripts ./scripts
COPY evaluation ./evaluation

EXPOSE 8000
CMD ["uvicorn", "medagent.main:application", "--host", "0.0.0.0", "--port", "8000"]
