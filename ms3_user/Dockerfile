FROM python:3.11-slim

WORKDIR /app

# libgomp1: OpenMP runtime needed by xgboost / scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY ms3_user/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ms3_user/ ./ms3_user/
COPY shared/ ./shared/

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "ms3_user.main:app", "--host", "0.0.0.0", "--port", "8002"]
