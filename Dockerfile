FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt

RUN pip install \
    --no-cache-dir \
    -r /tmp/requirements.txt

COPY . /app

RUN useradd \
      --create-home \
      --uid 10001 \
      ace \
    && chown -R ace:ace /app

USER ace
