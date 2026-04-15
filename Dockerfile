FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PYTHONPATH=/app/app

WORKDIR /app
COPY app /app/app
COPY samples /app/samples
COPY README.md /app/README.md

ENTRYPOINT ["python3", "-m", "ebpf_ml_mao"]
