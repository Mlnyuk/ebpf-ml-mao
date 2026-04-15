FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/app

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app
COPY app /app/app
COPY samples /app/samples
COPY README.md /app/README.md

USER appuser
ENTRYPOINT ["python3", "-m", "ebpf_ml_mao"]
