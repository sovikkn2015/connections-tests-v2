FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY _shared/ _shared/

ENV NEWS_API_RATE_LIMIT_RPM="100"
ENV NEWS_API_RATE_LIMIT_BURST="10"
# NEWS_API_KEY must be provided at runtime (Rule 3)

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8002/'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8002"]
