"""
Time the Gemini models your key can use, so GEMINI_MODEL / GEMINI_FALLBACK_MODELS can be chosen from data.

    PYTHONPATH=. python scripts/benchmark_gemini.py                      # every flash / flash-lite model, 2 prompts each
    PYTHONPATH=. python scripts/benchmark_gemini.py --models gemini-3.7-flash,gemini-3.5-flash-lite
    PYTHONPATH=. python scripts/benchmark_gemini.py --variants           # also test generation-config options on the 2 fastest

Columns: seconds + HTTP status for a tiny prompt and for a coach-sized prompt, and the number of hidden "thinking"
tokens the model spent (a large number explains slow answers). Requests run 4 at a time; each is cut off at --timeout.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from shared import db as _env  # noqa: F401  (loads .env)
from ms3_user.services import gemini_client

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TINY = "Reply with exactly one word: OK"
COACH = ("You are NutriX AI Coach. In about 150 words, suggest a high-protein vegetarian snack for someone who wants to "
         "build muscle, with ingredients, quick steps and why it works.")
SKIP = ("tts", "image", "transcribe", "live", "audio", "robotics", "computer-use", "omni", "lyria", "antigravity",
        "deep-research", "nano", "gemma", "customtools", "argon", "embedding")


def call(model, prompt, key, timeout, generation_config=None):
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if generation_config:
        payload["generationConfig"] = generation_config
    start = time.perf_counter()
    try:
        r = httpx.post(URL.format(model=model), json=payload, headers={"x-goog-api-key": key}, timeout=timeout)
    except httpx.HTTPError as e:
        return {"s": time.perf_counter() - start, "status": type(e).__name__, "chars": 0, "thoughts": None, "note": ""}
    elapsed = time.perf_counter() - start
    note, chars, thoughts = "", 0, None
    if r.status_code == 200:
        data = r.json()
        try:
            chars = len(data["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, IndexError):
            note = "no text"
        thoughts = (data.get("usageMetadata") or {}).get("thoughtsTokenCount")
    else:
        note = gemini_client._error_message(r)[:70]
    return {"s": elapsed, "status": r.status_code, "chars": chars, "thoughts": thoughts, "note": note}


def usable_flash_models(key):
    r = httpx.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 200},
                  headers={"x-goog-api-key": key}, timeout=15)
    r.raise_for_status()
    names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    return sorted(n for n in names if "flash" in n and not any(s in n for s in SKIP))


def fmt(res):
    status = "ok" if res["status"] == 200 else str(res["status"])
    thoughts = "" if res["thoughts"] is None else f" think={res['thoughts']}"
    return f"{res['s']:5.1f}s {status:>12}{thoughts}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="comma separated; default: every flash/flash-lite model your key lists")
    ap.add_argument("--timeout", type=float, default=40.0)
    ap.add_argument("--variants", action="store_true", help="test generation-config options on the two fastest models")
    args = ap.parse_args()

    key = gemini_client.api_key()
    if not key:
        print("GEMINI_API_KEY is not set in .env")
        return 1
    models = [m.strip() for m in args.models.split(",")] if args.models else usable_flash_models(key)
    print(f"Benchmarking {len(models)} model(s), timeout {args.timeout:.0f}s per call...\n")

    jobs = [(m, name, prompt) for m in models for name, prompt in (("tiny", TINY), ("coach", COACH))]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda j: (j[0], j[1], call(j[0], j[2], key, args.timeout)), jobs))
    table = {}
    for model, name, res in results:
        table.setdefault(model, {})[name] = res

    print(f"{'model':34} | {'tiny prompt':30} | coach-sized prompt")
    print("-" * 100)
    ranked = sorted(table.items(), key=lambda kv: (kv[1]["coach"]["status"] != 200, kv[1]["coach"]["s"]))
    for model, r in ranked:
        extra = f"  {r['coach']['note']}" if r["coach"]["note"] else ""
        print(f"{model:34} | {fmt(r['tiny']):30} | {fmt(r['coach'])} ({r['coach']['chars']} chars){extra}")

    good = [m for m, r in ranked if r["coach"]["status"] == 200][:4]
    if good:
        print(f"\nSuggested .env:\n  GEMINI_MODEL={good[0]}\n  GEMINI_FALLBACK_MODELS={','.join(good[1:])}")
    else:
        print("\nNo model answered the coach prompt successfully: check the status column (503 = overloaded, ReadTimeout = too slow).")

    if args.variants and good:
        print("\nGeneration-config variants on the fastest models (coach prompt):")
        variants = {
            "baseline": None,
            "maxOutputTokens=400": {"maxOutputTokens": 400},
            "thinkingBudget=0": {"thinkingConfig": {"thinkingBudget": 0}},
            "thinkingLevel=low": {"thinkingConfig": {"thinkingLevel": "low"}},
            "thinkingLevel=minimal": {"thinkingConfig": {"thinkingLevel": "minimal"}},
        }
        for model in good[:2]:
            for label, cfg in variants.items():
                res = call(model, COACH, key, args.timeout, cfg)
                note = f"  {res['note']}" if res["note"] else ""
                print(f"  {model:30} {label:24} {fmt(res)} ({res['chars']} chars){note}")
        print("\nUse an accepted one in .env as, for example:\n"
              "  GEMINI_GENERATION_CONFIG={\"thinkingConfig\": {\"thinkingBudget\": 0}, \"maxOutputTokens\": 600}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
