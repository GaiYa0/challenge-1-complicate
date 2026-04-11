# ---- builder ----
FROM python:3.10-slim AS builder

# 安全更新：修复基础镜像中已修复的 OS 级 CVE（如 OpenSSL 等）
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
# setuptools>=82 含 jaraco.context>=6.1.0（CVE-2026-23949）；wheel>=0.46.2（CVE-2026-24049）
RUN pip install --no-cache-dir --upgrade "pip>=24" "setuptools>=82.0.0" "wheel>=0.46.2" \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime ----
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser -d /app appuser

COPY --from=builder /install /usr/local

# 与 builder 对齐，覆盖 slim 镜像自带的旧 setuptools/wheel 及其 vendored 依赖
RUN pip install --no-cache-dir --upgrade "setuptools>=82.0.0" "wheel>=0.46.2"

WORKDIR /app
COPY main.py .
COPY backend ./backend

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/live || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
