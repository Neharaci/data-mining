FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir duckdb pyarrow pandas boto3 psycopg[binary]

CMD ["python", "-c", "import time; time.sleep(1000000000)"]