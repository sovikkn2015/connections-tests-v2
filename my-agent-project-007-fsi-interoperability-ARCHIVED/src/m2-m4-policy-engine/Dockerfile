FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV OPA_URL="http://opa:8181"
ENV USE_LOCAL_EVALUATOR="false"

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8002/health'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
