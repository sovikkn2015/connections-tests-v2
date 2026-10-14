FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV MINIO_ENDPOINT="http://minio:9000"
ENV MINIO_ACCESS_KEY="minioadmin"
ENV MINIO_SECRET_KEY="minioadmin"
ENV LANGFUSE_URL="http://langfuse:3000"
ENV DATABASE_URL="postgresql://fsi007:localdev@postgres:5432/fsi007_m10"

EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8010/health'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8010"]
