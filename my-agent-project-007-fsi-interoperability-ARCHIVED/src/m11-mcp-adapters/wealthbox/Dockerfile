FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY _shared/ _shared/

# WEALTHBOX_API_KEY must be provided at runtime (Rule 3)

EXPOSE 8052

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8052/'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8052"]
