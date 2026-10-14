FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY protos/ protos/
COPY _shared/ _shared/

# EZE_GRPC_HOST, EZE_GRPC_PORT, EZE_CLIENT_ID, EZE_CLIENT_SECRET must be provided at runtime (Rule 3)

EXPOSE 8041

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8041/'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8041"]
