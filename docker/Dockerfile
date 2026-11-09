FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 QE_ROOT=/data TRADING_MODE=DEMO QE_IN_DOCKER=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY quantum_edge ./quantum_edge
COPY frontend ./frontend
COPY config ./config
COPY scripts ./scripts
VOLUME ["/data"]
