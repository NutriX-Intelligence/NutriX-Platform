"""
FSN B3: USDA FoodData Central per-100 g references for the 46 raw / non-Indian foods that v1 S4 could not score.

  search : cache the FDC search results (SR Legacy + Foundation) for every food, print the candidates.
  fetch  : fetch the food record of every id in MAPPING and write v2/fdc_mapping.csv + v2/fdc_reference_per100g.csv.

Needs FDC_API_KEY (read from the environment or the gitignored .env); the key is never written to disk or printed.
Raw API responses are cached in v2/fdc_cache/ (re-runs read the cache, no request). FDC limit: 1000 requests/hour/IP;
this script stops itself at MAX_REQUESTS per run and sleeps between requests.

Source preference: SR Legacy first, because every SR Legacy record carries Energy (nutrient 1008, kcal) and
carbohydrate by difference (1005); many Foundation records carry only Atwater energies (2047/2048) or no energy row.
A Foundation record is used only if it has nutrient 1008. The state chosen is the one the dataset photos show for
the class (raw produce; cooked where the class is a cooked food): marked `judgement` in the mapping CSV for audit.

  PYTHONPATH=. python scripts/fsn_b3_fdc.py search
  PYTHONPATH=. python scripts/fsn_b3_fdc.py fetch
"""
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / "docs" / "paper-upgrade" / "results" / "fsn"
OUT = V1 / "v2"
CACHE = OUT / "fdc_cache"
API = "https://api.nal.usda.gov/fdc/v1"
MAX_REQUESTS = 300
SLEEP_S = 0.6
NUTRIENTS = {"kcal": 1008, "protein": 1003, "carbs": 1005, "fat": 1004}

# food -> search query
QUERY = {
    "apple": "apples raw with skin", "artichoke": "artichokes globe raw", "avocado": "avocados raw all commercial varieties",
    "banana": "bananas raw", "beans": "beans snap green raw", "beet": "beets raw", "bell pepper": "peppers sweet red raw",
    "bitter gourd": "balsam-pear bitter gourd pods raw", "blueberry": "blueberries raw", "bottle gourd": "gourd white-flowered calabash raw",
    "broccoli": "broccoli raw", "brussels sprouts": "brussels sprouts raw", "cabbage": "cabbage raw", "capsicum": "peppers sweet green raw",
    "carrot": "carrots raw", "cauliflower": "cauliflower raw", "celery": "celery raw", "chicken": "chicken broilers or fryers meat only raw",
    "chickpeas": "chickpeas mature seeds cooked boiled without salt", "corn": "corn sweet yellow raw", "cucumber": "cucumber with peel raw",
    "egg": "egg whole raw fresh", "eggplant": "eggplant raw", "garlic": "garlic raw", "grape": "grapes red or green raw",
    "green brinjal": "eggplant raw", "hot pepper": "peppers hot chili green raw", "lettuce": "lettuce green leaf raw",
    "minced meat": "beef ground 80% lean meat 20% fat raw", "onion": "onions raw", "orange": "oranges raw all commercial varieties",
    "papaya": "papayas raw", "pattypan squash": "squash summer scallop raw", "pea": "peas green raw", "peach": "peaches yellow raw",
    "pear": "pears raw", "pineapple": "pineapple raw all varieties", "potato": "potatoes flesh and skin raw", "pumpkin": "pumpkin raw",
    "radish": "radishes raw", "raspberry": "raspberries raw", "strawberry": "strawberries raw", "sweet potato": "sweet potato raw unprepared",
    "tomato": "tomatoes red ripe raw year round average", "vegetable marrow": "squash summer zucchini includes skin raw",
    "watermelon": "watermelon raw",
}

# food -> (fdcId, rule). Filled after `search` from the cached candidates; every id is checked in `fetch`.
E, J = "exact (generic raw entry)", "judgement"
MAPPING = {
    "apple": (171688, E + "; with skin"), "artichoke": (169205, E), "avocado": (171705, E), "banana": (173944, E),
    "beans": (169961, J + ": class 'beans' taken as green snap beans"), "beet": (169145, E),
    "bell pepper": (170108, J + ": red (capsicum class is mapped to green)"), "bitter gourd": (168393, E + "; pods"),
    "blueberry": (171711, E), "bottle gourd": (169232, E + "; calabash = bottle gourd"), "broccoli": (170379, E),
    "brussels sprouts": (170383, E), "cabbage": (169975, E), "capsicum": (170427, J + ": green"), "carrot": (170393, E),
    "cauliflower": (169986, E), "celery": (169988, E), "chicken": (171052, J + ": raw meat only (cooked state unknown)"),
    "chickpeas": (173757, J + ": cooked, boiled (as served); dry seeds would be ~364 kcal"), "corn": (169998, E + "; sweet yellow"),
    "cucumber": (168409, E + "; with peel"), "egg": (171287, J + ": whole raw (boiled egg is close)"), "eggplant": (169228, E),
    "garlic": (169230, E), "grape": (174683, E), "green brinjal": (169228, J + ": eggplant, raw"),
    "hot pepper": (170497, J + ": green chili"), "lettuce": (169249, J + ": green leaf"),
    "minced meat": (174036, J + ": beef 80/20 raw; mutton/chicken mince would differ"), "onion": (170000, E),
    "orange": (169097, E), "papaya": (169926, E), "pattypan squash": (169289, E + "; scallop squash = pattypan"),
    "pea": (170419, E + "; green peas"), "peach": (169928, E), "pear": (169118, E), "pineapple": (169124, E),
    "potato": (170026, E + "; flesh and skin"), "pumpkin": (168448, E), "radish": (169276, E), "raspberry": (167755, E),
    "strawberry": (167762, E), "sweet potato": (168482, E), "tomato": (170457, E),
    "vegetable marrow": (169291, J + ": zucchini (summer squash)"), "watermelon": (167765, E),
}


def _key():
    k = os.getenv("FDC_API_KEY")
    if not k:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("FDC_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
    return k or None


class Client:
    def __init__(self):
        import httpx
        self.key = _key()
        if not self.key:
            sys.exit("FDC_API_KEY is not set: skipping B3")
        self.http = httpx.Client(timeout=30)
        self.n = 0

    def get(self, cache_name, path, params):
        f = CACHE / cache_name
        if f.exists():
            return json.loads(f.read_text())
        if self.n >= MAX_REQUESTS:
            sys.exit(f"stopping at {MAX_REQUESTS} requests this run (FDC limit 1000/h)")
        time.sleep(SLEEP_S)
        r = self.http.get(f"{API}/{path}", params={**params, "api_key": self.key})
        self.n += 1
        if r.status_code != 200:
            sys.exit(f"FDC HTTP {r.status_code} on {path} (no key in this message)")
        data = r.json()
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, indent=1))      # response body only: the request URL (with the key) is not stored
        return data


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def nutrient_values(food_json):
    """per-100 g kcal/protein/carbs/fat from a /food/{id} record (SR Legacy / Foundation are per 100 g)."""
    out = {}
    for fn in food_json.get("foodNutrients", []):
        nid = (fn.get("nutrient") or {}).get("id", fn.get("nutrientId"))
        for k, want in NUTRIENTS.items():
            if nid == want and "amount" in fn:
                out[k] = float(fn["amount"])
            elif nid == want and "value" in fn:
                out[k] = float(fn["value"])
    return out


def search():
    c = Client()
    for food, q in QUERY.items():
        data = c.get(f"search_{slug(food)}.json", "foods/search",
                     {"query": q, "dataType": "SR Legacy,Foundation", "pageSize": 8})
        print(f"\n## {food}  (q={q!r})")
        for h in data.get("foods", [])[:8]:
            kcal = next((n.get("value") for n in h.get("foodNutrients", []) if n.get("nutrientId") == 1008), None)
            print(f"   {h['fdcId']:>8} {h.get('dataType', ''):<11} kcal={kcal} {h['description']}")
    print(f"\nrequests this run: {c.n}")


def fetch():
    missing = [f for f in QUERY if f not in MAPPING]
    if missing:
        sys.exit(f"MAPPING incomplete: {missing}")
    c = Client()
    maps, refs = [], []
    for food, (fdc_id, rule) in MAPPING.items():
        d = c.get(f"food_{fdc_id}.json", f"food/{fdc_id}", {})
        v = nutrient_values(d)
        maps.append(dict(food=food, fdc_id=fdc_id, data_type=d.get("dataType"), description=d.get("description"),
                         rule=rule, search_query=QUERY[food], has_all_4=all(k in v for k in NUTRIENTS)))
        refs.append(dict(food=food, ref_source=f"USDA FDC {d.get('dataType')}", ref_code=f"FDC_{fdc_id}",
                         ref_name=d.get("description"), **{f"ref_{k}": v.get(k) for k in NUTRIENTS}))
    for name, rows in (("fdc_mapping.csv", maps), ("fdc_reference_per100g.csv", refs)):
        with open(OUT / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(f"{len(maps)} foods mapped; incomplete: {[m['food'] for m in maps if not m['has_all_4']]}; requests this run: {c.n}")


if __name__ == "__main__":
    {"search": search, "fetch": fetch}[sys.argv[1]]()
