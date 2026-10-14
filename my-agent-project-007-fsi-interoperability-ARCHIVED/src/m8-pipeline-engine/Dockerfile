FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV M6_URL="http://m6-mcp-gateway:8006"
ENV DATABASE_URL="postgresql://fsi007:localdev@postgres:5432/fsi007_m8"
ENV AWS_DEFAULT_REGION="us-east-1"

EXPOSE 8008

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8008/health'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "m8_pipeline_engine.app:app", "--host", "0.0.0.0", "--port", "8008"]
