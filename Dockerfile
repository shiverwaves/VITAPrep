FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Mount ./data to provide distribution DBs and persist runtime scenarios.
# Any .sqlite files added to data/ (e.g. distributions_ca_2023.sqlite)
# are automatically available without rebuilding.
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
