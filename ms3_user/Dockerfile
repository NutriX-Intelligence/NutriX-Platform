FROM python:3.11-slim

WORKDIR /app

COPY ms3_user/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ms3_user/ ./ms3_user/
COPY shared/ ./shared/

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "ms3_user.main:app", "--host", "0.0.0.0", "--port", "8002"]
