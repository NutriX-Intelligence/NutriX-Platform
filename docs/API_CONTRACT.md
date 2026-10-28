# NutriX API Contract (app ↔ backend)

> The single reference for the Flutter app. Everything goes through the **API Gateway** (`http://<host>:8000`).
> Machine-readable spec: [`docs/api/openapi_ms3.json`](api/openapi_ms3.json) (regenerate with `PYTHONPATH=. python scripts/export_openapi.py`).
> Version: **v1** (`/api/v1/...`). The old unprefixed paths still work (see "Legacy paths") but are deprecated.

## 1. Conventions

| Topic | Rule |
|---|---|
| Base URL | `http://<gateway-host>:8000`, configurable in the app (LAN IP for device testing) |
| Content type | JSON (`Content-Type: application/json`), except uploads (`multipart/form-data`) and the SSE stream |
| Auth | `Authorization: Bearer <access_token>` on every call except the four public auth routes |
| Dates / times | `log_date`, `date`: `YYYY-MM-DD` (**UTC day**); timestamps: ISO-8601 UTC |
| Units | grams (`*_g`), kilocalories (`calories`, `energy_kcal`), millilitres (`*_ml`), centimetres, kilograms |
| Request tracing | Every response carries `X-Request-ID`; send your own `X-Request-ID` to correlate logs |
| CORS | Allowed origins come from `CORS_ORIGINS` (default `*`) |
| Errors | HTTP status + `{"detail": "..."}` (validation errors: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`) |

Status codes: `200/201` success · `400` bad input · `401` missing/invalid/expired token (sign in again) · `403` the request names another user's data · `404` not found · `422` validation error · `503` AI/upstream service unavailable · `502/504` a backend service is down / timed out (gateway).

## 2. Authentication

1. `POST /api/v1/auth/register` or `POST /api/v1/auth/login` or `POST /api/v1/auth/google` → `{"access_token", "token_type": "bearer", "is_new_user", "user": {...}}`.
2. Store `access_token` in secure storage (Android Keystore). Default lifetime is **30 days** (`JWT_EXPIRY_HOURS`).
3. Send `Authorization: Bearer <token>` on every request. On `401`, discard the token and show sign-in.
4. `user.is_onboarded == false` → show the onboarding screens, then `POST /api/v1/user/profile` (body below).
5. The token's subject is the **numeric user id**. A user can only read or write their own data: any request whose path, query, body or form names a different user id gets `403`.

Public routes: `POST /api/v1/auth/register | login | google | reset-password` (and `GET /health`).

**Google sign-in:** the app gets a Google ID token (`google_sign_in`) and sends `{"id_token": "..."}` to `/auth/google`. The server checks it was issued for one of its `GOOGLE_CLIENT_ID` values (comma separated: web / android / ios). In `ENV=dev` the mock tokens `mock-google-<name>@example.com` are accepted.

## 3. Endpoints (canonical path → legacy path the old app used)

### Account & profile
| Method | Path | Legacy | Notes |
|---|---|---|---|
| POST | `/api/v1/auth/register` | `/api/auth/register` | `{email, password(≥6), name, age?, gender?, height?, weight?, activity_level?, goal?, preferences?}` |
| POST | `/api/v1/auth/login` | `/api/auth/login` | `{email, password}` (email must be a real-looking domain; `.local` is rejected) |
| POST | `/api/v1/auth/google` | `/api/auth/google` | `{id_token}` |
| POST | `/api/v1/auth/reset-password` | `/api/auth/reset-password` | stub: no e-mail is sent yet |
| GET/POST | `/api/v1/auth/me` | `/api/auth/me` | current profile with BMI/BMR/TDEE and targets |
| POST | `/api/v1/user/profile` | `/calculate-profile` | save onboarding/profile, recomputes targets; `email` must be the caller's |
| GET | `/api/v1/user/targets` | – | **new**: same payload as `/auth/me`, no id in the URL |
| GET | `/api/v1/users/{user_id}/targets` | `/users/{user_id}/targets` | `user_id` must be the caller |
| GET | `/api/v1/users/{user_id}/weight-history` · `/meal-plans` | `/users/{id}/...` | |
| GET / PUT | `/api/v1/settings` | `/api/settings` | `PUT {key, value}` |
| GET / POST | `/api/v1/search-history` | `/api/search-history` | `POST {query}` |

### Dashboard (new)
| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/user/daily-summary?date=YYYY-MM-DD` | `{user_id, date, source: "redis"\|"db", consumed{calories,protein_g,carbs_g,fat_g}, targets{...}, remaining{...}, percent{...}, meals_count, latest_item, updated_at}`. Served from Redis (<10 ms); poll it or use the stream |
| GET | `/api/v1/user/history?from=&to=&page=1&page_size=50` | all sources (scale, manual, fast food...); default last 7 days; `{from,to,page,page_size,total,items[{id,log_date,meal_type,food_name,weight_g,calories,protein,carbs,fat,source}]}` |
| GET | `/api/v1/user/stream` | **Server-Sent Events** (see §4) |

### Logging
| Method | Path | Legacy | Notes |
|---|---|---|---|
| POST | `/api/v1/meal-logs` | `/api/meal-logs` | `{user_id, food_name, meal_type?, calories, protein, carbs, fat, weight_g?, source?, log_date?}`; `source`: `manual` (default) · `fast_food` · `barcode` · `homely` · `recipe` · `ocr_label`; `201` + the log |
| GET | `/api/v1/meal-logs/today/{user_id}?log_date=` | `/api/meal-logs/today/{id}` | totals, targets and the day's logs |
| DELETE | `/api/v1/meal-logs/{log_id}` | `/api/meal-logs/{id}` | only your own; updates the dashboard |
| POST | `/api/v1/water-logs` · GET `/water-logs/today/{user_id}` · `/water-logs/history/{user_id}?days=` · DELETE `/water-logs/{id}` | `/api/water-logs...` | `{user_id, amount_ml}` |
| POST | `/api/v1/weight-logs` · DELETE `/weight-logs/{id}` | `/track-weight`, `/api/weight-logs/{id}` | `{user_id, weight, logged_at?, adherence?}` |
| GET | `/api/v1/analytics/{user_id}` · `/analytics/{user_id}/history?metric_name=&limit=` | `/api/analytics/...` | |

> Meals logged by the **smart scale** appear automatically in `history` and `daily-summary` with `source` = `esp32_yolo`, `esp32_qwen_vlm` (the vision model named the food) or `llm-timeout` (0 kcal: the AI service was down).

### Food, recipes, plans
| Method | Path | Legacy |
|---|---|---|
| POST | `/api/v1/foods/recommend` | `/recommend-foods` |
| GET | `/api/v1/recipes/top` · `/recipes/search?q=` · `/recipes/{recipe_code}` | `/recipes/...` |
| POST | `/api/v1/recipes/recommend` · `/recipes/filter` · `/recipes/generate-instructions` | `/recipes/...`, `/api/recipes/generate-instructions` |
| POST | `/api/v1/meal-plans/generate` | `/generate-meal-plan` |
| GET | `/api/v1/fast-food/chains` · `/fast-food/grouped?brand=&diet_filter=&q=&category=` | `/api/fast-food/...` |
| POST | `/api/v1/classify` · `/classify/substitutions` | `/api/classify...` |
| GET/POST | `/api/v1/homely/builder-defaults`, `/homely-meals/calculate`, `/create`, `/user/{id}`, `/search`, `/pending`, `/{id}`, `/{id}/review`, `/review/{id}` | `/api/homely...` |

### Barcode, OCR (image uploads: JPEG/PNG, `multipart/form-data`, field `file`)
| Method | Path | Legacy |
|---|---|---|
| GET | `/api/v1/barcode/{barcode}?diet_type=` | `/api/barcode/{barcode}` |
| POST | `/api/v1/barcode/scan-image` (+ optional `diet_type`) | `/api/barcode/scan-image` |
| POST | `/api/v1/barcode/manual` · `/barcode/alternatives` | `/api/barcode/...` |
| POST | `/api/v1/ocr/upload` (+ optional `meal_type`, `food_name` to log it) | `/api/ocr` |

### AI (Gemini, then the local model, then canned text)
| Method | Path | Response |
|---|---|---|
| POST | `/api/v1/ai/coach` `{message, history?[{role,message}]}` | `{reply, source}` where `source` is `gemini`, `local` or `offline` |
| POST | `/api/v1/ai/diet-plan` `{user_id}` | `{plan, source}` |
| POST | `/api/v1/ai/recipe-generator` `{ingredients}` | `{recipe, source}` |
| POST | `/api/v1/recipes/generate-instructions` `{recipe_name, ingredients?, recipe_code?}` | `{instructions, source}`; `503` only when Gemini and the local model are both unavailable |

`source` tells you who answered: `gemini`; `local` (the on-premise Qwen model on MS2, used when Gemini is overloaded, down or not configured: shorter, less polished answers); or `offline` (a canned answer because both failed). The app can show a subtle hint for `local` / `offline`; it is never an error.

### Scale (device only, not for the app)
`POST /api/v1/ingest/weight-frame` with `Device-Token` + `User-ID` headers. Unknown `User-ID` → `404`.

## 4. Live dashboard stream (SSE)

```
GET /api/v1/user/stream        Authorization: Bearer <token>        Accept: text/event-stream
```
Frames:
```
event: summary
data: {"date":"2026-10-27","source":"snapshot","consumed":{...},"targets":{...},"remaining":{...},"percent":{...},"meals_count":1,"latest_item":"Banana","updated_at":"..."}

: ping                         <- heartbeat comment every 15 s (ignore)
```
The first frame (`source: "snapshot"`) is the current state; later frames (`source: "live"`) arrive whenever a meal is added or deleted, from any source. Use an HTTP client that can set headers (a browser `EventSource` cannot). Reconnect with backoff if the stream ends. If SSE is not convenient, polling `daily-summary` every few seconds gives the same data.

## 5. Legacy paths

While `ENABLE_LEGACY_ROUTES=true` (default) the old unprefixed paths in the tables above (e.g. `/api/meal-logs`, `/recipes/top`, `/calculate-profile`) keep working through the gateway with identical behaviour; only the token format changed (existing sessions need one fresh sign-in). They are hidden from OpenAPI and will be removed after the app migrates to `/api/v1`.

## 6. Known gaps (backend work still to come)
Human-in-the-loop confirmation of scale guesses (`/api/v1/hitl/confirm`), push notifications, the agent chat (`/api/v1/agent/query`), refresh tokens, and e-mail delivery for password reset.
