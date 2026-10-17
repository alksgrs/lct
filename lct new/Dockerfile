FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY greenplan ./greenplan
COPY data ./data

ENTRYPOINT ["python", "-m", "greenplan.cli"]
