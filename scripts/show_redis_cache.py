import sys
import json
from datetime import datetime
from shared.redis_client import get_redis_client, get_daily_macros

def main():
    client = get_redis_client()
    today_str = datetime.utcnow().date().isoformat()
    user_id = 1
    
    print("\n" + "="*70)
    print(f"          NUTRIX REDIS LIVE CACHE — USER {user_id} ({today_str})")
    print("="*70)
    
    data = get_daily_macros(user_id, today_str)
    if not data:
        print("No Redis live data found for today yet. Trigger a scale capture!")
    else:
        print(f"Key: user:{user_id}:macros:{today_str}")
        print("-" * 70)
        print(f"  • Today's Total Calories : {data.get('calories', 0)} kcal")
        print(f"  • Total Protein          : {data.get('protein_g', 0)} g")
        print(f"  • Total Carbs            : {data.get('carbs_g', 0)} g")
        print(f"  • Total Fat              : {data.get('fat_g', 0)} g")
        print(f"  • Meals Logged Today     : {data.get('meals_count', 0)}")
        print(f"  • Most Recent Item       : {data.get('latest_item', 'N/A')}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
