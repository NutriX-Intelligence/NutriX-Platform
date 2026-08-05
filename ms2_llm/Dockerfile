FROM python:3.11-slim

WORKDIR /app

COPY ms2_llm/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ms2_llm/ ./ms2_llm/
COPY shared/ ./shared/

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "ms2_llm.main:app", "--host", "0.0.0.0", "--port", "8003"]
