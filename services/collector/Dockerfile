FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install uv
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app/ ./app/
ENV PYTHONPATH=/app
CMD ["python", "-m", "app.main"]
