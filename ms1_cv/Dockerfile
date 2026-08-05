FROM ultralytics/ultralytics:latest

WORKDIR /app

COPY ms1_cv/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ms1_cv/ ./ms1_cv/
COPY shared/ ./shared/

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "ms1_cv.main:app", "--host", "0.0.0.0", "--port", "8001"]
