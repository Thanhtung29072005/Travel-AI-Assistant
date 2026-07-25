# ── Build Stage ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Cài đặt các công cụ build cơ bản nếu cần
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt và cài đặt wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ── Production Stage ─────────────────────────────────────────
FROM python:3.11-slim AS runner

WORKDIR /app

# Khai báo các biến môi trường mặc định
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0

# Copy installed dependencies từ builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy source code của ứng dụng
COPY app/ ./app/

# Port exposure
EXPOSE 8000

# Khởi động ứng dụng bằng uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
