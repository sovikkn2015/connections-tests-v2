FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8020

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8020/health'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8020"]
