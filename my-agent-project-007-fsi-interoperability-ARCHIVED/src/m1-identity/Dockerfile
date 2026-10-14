FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV M1_PRIVATE_KEY_PEM=""
ENV M1_PUBLIC_KEY_PEM=""
ENV KEYCLOAK_URL="http://keycloak:8080"
ENV DATABASE_URL="postgresql://fsi007:localdev@postgres:5432/fsi007_m1"

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8001/health'); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "entrypoint:app", "--host", "0.0.0.0", "--port", "8001"]
