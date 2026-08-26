import os

MS1_CV_URL     = os.getenv("MS1_CV_URL",     "http://localhost:8001")
MS2_LLM_URL    = os.getenv("MS2_LLM_URL",    "http://localhost:8003")
MS3_USER_URL   = os.getenv("MS3_USER_URL",   "http://localhost:8002")
MS4_AGENTS_URL = os.getenv("MS4_AGENTS_URL", "http://localhost:8004")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-insecure-secret")
JWT_ALGORITHM  = os.getenv("JWT_ALGORITHM",  "HS256")
DEVICE_TOKEN   = os.getenv("DEVICE_TOKEN",   "NutriX_ESP32_SECURE_TOKEN")
