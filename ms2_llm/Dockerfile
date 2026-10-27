# CUDA + PyTorch base. The model weights are NOT baked in: mount them and set VLM_MODEL_PATH
# (see docker-compose.yml).
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

WORKDIR /app

COPY ms2_llm/requirements.txt ms2_llm/requirements-vlm.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-vlm.txt

COPY ms2_llm/ ./ms2_llm/
COPY shared/ ./shared/

ENV PYTHONUNBUFFERED=1

# No --reload: every reload would re-read the ~4 GB model
CMD ["uvicorn", "ms2_llm.main:app", "--host", "0.0.0.0", "--port", "8003"]
