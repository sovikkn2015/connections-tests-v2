FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY _shared/ _shared/

# FACTSET_MCP_ENDPOINT, FACTSET_OAUTH_CLIENT_ID, FACTSET_OAUTH_CLIENT_SECRET must be provided at runtime (Rule 3)

EXPOSE 8042

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8042/'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8042"]
