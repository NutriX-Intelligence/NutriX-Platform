#!/usr/bin/env bash
# Read-only preflight for a NutriX test session. Prints PASS / WARN / FAIL; never prints secrets; changes nothing.
#   bash scripts/preflight_check.sh              # infra, config, model files, GPU, dev account
#   bash scripts/preflight_check.sh --services   # also check that the 5 services answer /health
cd "$(dirname "$0")/.." || exit 1
FAILS=0; WARNS=0
pass() { printf "  [PASS] %s\n" "$1"; }
warn() { printf "  [WARN] %s\n" "$1"; WARNS=$((WARNS+1)); }
fail() { printf "  [FAIL] %s\n" "$1"; FAILS=$((FAILS+1)); }
envval() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"'"; }

echo "== 1. Docker (Postgres + Redis)"
for c in nutrix-postgres nutrix-redis; do
  st=$(docker inspect -f '{{.State.Health.Status}}' "$c" 2>/dev/null)
  [ "$st" = "healthy" ] && pass "$c healthy" || fail "$c not healthy (run: docker compose up -d postgres redis)"
done

echo "== 2. .env"
[ -f .env ] && pass ".env exists" || fail ".env missing"
[ -n "$(envval DEVICE_TOKEN)" ] && pass "DEVICE_TOKEN set (value hidden)" || fail "DEVICE_TOKEN empty"
[ "$(envval ENV)" = "dev" ] && pass "ENV=dev" || warn "ENV is '$(envval ENV)' (dev-ui and dev JWT secret need dev)"
[ "$(envval AUTO_CREATE_DEV_USER)" = "true" ] && pass "AUTO_CREATE_DEV_USER=true" || warn "AUTO_CREATE_DEV_USER is '$(envval AUTO_CREATE_DEV_USER)'"
[ "$(envval APP_TIMEZONE)" = "Asia/Kolkata" ] && pass "APP_TIMEZONE=Asia/Kolkata" || warn "APP_TIMEZONE is '$(envval APP_TIMEZONE)'"
thr=$(envval YOLO_CONF_THRESHOLD); [ -n "$thr" ] && pass "YOLO_CONF_THRESHOLD=$thr" || warn "YOLO_CONF_THRESHOLD unset (default 0.5)"
[ -n "$(envval GEMINI_API_KEY)" ] && pass "GEMINI_API_KEY set (needed only for barcode/OCR/AI coach)" || warn "GEMINI_API_KEY empty: barcode/OCR/coach use offline fallbacks"

echo "== 3. Model files"
vp=$(envval VLM_MODEL_PATH)
if [ -n "$vp" ] && [ -f "$vp/model.safetensors" ]; then pass "Qwen3-VL snapshot readable"; else fail "VLM_MODEL_PATH missing or has no model.safetensors"; fi
[ -f backend/services/ingestion/best.pt ] && pass "best.pt present" || warn "backend/services/ingestion/best.pt missing"
[ -f ms1_cv/nutrix_yolo_custom.pt ] && pass "ms1_cv/nutrix_yolo_custom.pt present" || warn "ms1_cv/nutrix_yolo_custom.pt missing"

echo "== 4. Python env"
if [ -x .venv/bin/python ]; then
  .venv/bin/python -c "import torch, transformers, qwen_vl_utils, ultralytics, fastapi, sqlalchemy; import sys; sys.exit(0 if torch.cuda.is_available() else 3)" 2>/dev/null
  rc=$?
  [ $rc -eq 0 ] && pass "deps import, CUDA available" || { [ $rc -eq 3 ] && fail "deps ok but CUDA NOT available" || fail "a dependency fails to import (pip install -r requirements.txt ...)"; }
else fail ".venv missing"; fi

echo "== 5. GPU"
if command -v nvidia-smi >/dev/null; then
  read -r used total < <(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits | tr -d ' ' | tr ',' ' ')
  free=$((total-used))
  echo "         GPU memory used ${used} / ${total} MiB (free ${free})"
  [ "$free" -ge 4800 ] && pass "enough free VRAM to start MS2 now" || warn "free VRAM < 4.8 GB: fine if MS2 is already running, otherwise close GPU apps"
else fail "nvidia-smi not found"; fi

echo "== 6. Database"
dbq() { docker exec nutrix-postgres psql -U nutrix -d nutrix_db -tAc "$1" 2>/dev/null; }
u=$(dbq "SELECT id||'|'||email FROM users WHERE id=1")
[ "$u" = "1|dev@nutrix.dev" ] && pass "user 1 = dev@nutrix.dev" || fail "user 1 is '${u:-missing}' (run scripts/create_dev_user.py)"
[ "$(dbq "SELECT count(*) FROM foods")" -gt 1000 ] 2>/dev/null && pass "foods table seeded ($(dbq "SELECT count(*) FROM foods") rows)" || warn "foods table small or unreadable"
[ "$(dbq "SELECT count(*) FROM system_prompt_registry WHERE prompt_key IN ('vision_infer_v2','nutrition_lookup_v2')")" = "2" ] 2>/dev/null && pass "MS2 prompts seeded" || warn "MS2 prompts missing (python shared/seeders/seed_prompts.py)"

if [ "$1" = "--services" ]; then
  echo "== 7. Services"
  for p in 8000 8001 8002 8003; do
    s=$(curl -s -m 5 localhost:$p/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['service'], d['status'])" 2>/dev/null)
    [ -n "$s" ] && pass "$p $s" || fail "$p DOWN"
  done
  curl -s -m 5 localhost:8004/health >/dev/null && pass "8004 up" || warn "8004 (MS4) down: expected"
  curl -s -m 5 localhost:8003/health | grep -q '"status": *"ok"' && pass "MS2 VLM loaded" || warn "MS2 VLM not reported ok yet"
fi

echo
echo "RESULT: $FAILS fail, $WARNS warn"
[ "$FAILS" -eq 0 ]
