FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY _shared/ _shared/

ENV ALPHA_VANTAGE_RATE_LIMIT_RPM="5"
ENV ALPHA_VANTAGE_RATE_LIMIT_BURST="5"
# ALPHA_VANTAGE_API_KEY must be provided at runtime (Rule 3)

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8001/'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8001"]
