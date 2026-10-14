FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV REDIS_URL="redis://redis:6379"
ENV M1_URL="http://m1-identity:8001"
ENV M2_URL="http://m2-m4-policy:8002"
ENV M4_URL="http://m2-m4-policy:8002"
ENV M7_URL="http://m7-schema-translators:8007"
ENV M10_URL="http://m10-audit-logger:8010"

EXPOSE 8006

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8006/health'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8006"]
