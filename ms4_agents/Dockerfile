FROM python:3.11-slim

WORKDIR /app

COPY ms4_agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ms4_agents/ ./ms4_agents/
COPY shared/ ./shared/

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "ms4_agents.main:app", "--host", "0.0.0.0", "--port", "8004"]
