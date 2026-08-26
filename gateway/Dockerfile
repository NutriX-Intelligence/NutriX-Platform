FROM python:3.11-slim

# Create a non-root user
RUN groupadd -r gateway && useradd -r -g gateway gateway

WORKDIR /app

COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway/ ./gateway/
COPY shared/ ./shared/

# Set ownership
RUN chown -R gateway:gateway /app

# Switch to non-root user
USER gateway

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
