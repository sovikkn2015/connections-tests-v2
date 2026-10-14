FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY _shared/ _shared/

# No credentials in image — provide at runtime via Vault/Secrets Manager (Rule 20)

EXPOSE 8030

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8030/health'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8030"]
