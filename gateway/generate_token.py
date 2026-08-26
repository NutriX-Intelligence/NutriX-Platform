import time
import os
import sys

# Ensure project root is in sys.path so it can be run directly from any directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jose import jwt
from gateway.config import JWT_SECRET_KEY, JWT_ALGORITHM

def get_test_token(user_id: str = "1", exp_hours: int = 1) -> str:
    payload = {
        "sub": str(user_id),
        "exp": int(time.time()) + (exp_hours * 3600)
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

if __name__ == "__main__":
    token = get_test_token()
    print("\n=== NutriX Test JWT Token ===")
    print(token)
    print("\n=== Ready-to-use curl command ===")
    print(f'curl -i -H "Authorization: Bearer {token}" http://localhost:8000/api/v1/user/daily-summary\n')
