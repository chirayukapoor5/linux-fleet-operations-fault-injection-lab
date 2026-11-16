FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -r -u 10001 fleetops && mkdir -p /data && chown fleetops:fleetops /data
COPY app/ ./app/
USER fleetops
ENV FLEETOPS_DB=/data/fleetops.sqlite3
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
