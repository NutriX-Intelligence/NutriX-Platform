# NutriX backend: handoff for the app developer

You are updating the existing NutriX Flutter app so it builds against the rebuilt backend. This page is the starting point; **the work plan is `APP_BUILD_GUIDE.md`**; the full API is in `API_CONTRACT.md`. **The old unprefixed routes still work**, so the first goal is only: change the base URL, sign in, and see data.

## 1. What is in this package

| File | What it is |
|---|---|
| `APP_HANDOFF.md` | this page |
| `APP_BUILD_GUIDE.md` | **the work plan**: how to update the app to this backend, stage by stage, with the networking code, the old-to-new path table and a definition of done |
| `API_CONTRACT.md` | the complete app-facing contract: auth, every endpoint, request/response shapes, errors, live stream |
| `openapi_ms3.json` | machine-readable spec (generate Dart models from it, see §8). Some endpoints return plain JSON objects, so for those the tables in `API_CONTRACT.md` are the reference |
| `nutrix_requests.http` | ready-to-run sample requests (VS Code "REST Client" extension, or copy into Postman/Insomnia) |

## 2. The backend you talk to

Everything goes through one door, the **API Gateway**. You never call the internal services directly.

```
Base URL:        <<FILL IN: e.g. https://xxxx.trycloudflare.com  or  http://192.168.x.x:8000>>
Test account:    dev@nutrix.dev   /   nutrix123      (user id 1, has seeded data)
Health check:    GET <base>/health/all      (all services should say healthy; ms4_agents "down" is expected, it is not built yet)
```
- Over plain `http://` on Android 9+, add `android:usesCleartextTraffic="true"` to the `<application>` tag while testing.
- Android emulator reaching a backend on your own PC: use `http://10.0.2.2:8000`.
- Email addresses must have a real-looking domain (`@example.com` is fine, `@something.local` is rejected).
- The backend serves **CORS for any origin** during development, so Flutter web works.

## 3. First ten minutes

1. `GET <base>/health/all`: confirm the backend is up.
2. `POST /api/v1/auth/login` with the test account: you get `{access_token, token_type, user}`.
3. Send `Authorization: Bearer <access_token>` on **every** call from now on.
4. `GET /api/v1/user/daily-summary`: the numbers behind the home-screen rings.
5. `POST /api/v1/meal-logs` (see the `.http` file), then `GET /api/v1/user/history` and `daily-summary` again: the meal appears and the totals change.
6. Ask me to trigger a smart-scale scan: it appears in `history` / `daily-summary` / the stream with no action from the app.

## 4. Authentication in one paragraph

Register or sign in (email + password, or Google) to get a JWT valid for 30 days. Store it securely and send it as a Bearer token. **`401` means sign in again** (expired, invalid, or the account does not exist). **`403` means the request names another user's id** (path, query, body or form): the server only lets a user touch their own data. Existing sessions from the old backend stop working once; users sign in again. Details and the Google sign-in setup are in `API_CONTRACT.md` §2.

## 5. Which endpoint feeds which screen

| Screen | Endpoints |
|---|---|
| Onboarding / profile | `POST /auth/register`, `POST /user/profile` (saves profile, recomputes targets), `GET /auth/me` (`is_onboarded` tells you whether to show onboarding) |
| Home dashboard (rings, today) | `GET /user/daily-summary` (poll) or `GET /user/stream` (live, see §6); `GET /user/history` for the diary list; `GET /analytics/{id}` for charts |
| Meal diary / logging | `POST /meal-logs`, `DELETE /meal-logs/{id}`, `GET /meal-logs/today/{id}`; water: `/water-logs...`; weight: `/weight-logs` |
| Fast food | `GET /fast-food/chains`, `GET /fast-food/grouped?brand=&diet_filter=` then log with `POST /meal-logs` (`source: "fast_food"`) |
| Kitchen / recipes | `GET /recipes/top`, `/recipes/search?q=`, `/recipes/{code}`, `POST /recipes/recommend` (pantry ingredients), `/recipes/filter`, `/recipes/generate-instructions`, `POST /foods/recommend` |
| Meal plan | `POST /meal-plans/generate` |
| Barcode & scan | `GET /barcode/{code}` (typed/scanned number), `POST /barcode/scan-image` (photo of the barcode), `POST /ocr/upload` (photo of a nutrition label), `POST /barcode/manual`, `POST /barcode/alternatives` |
| Homely builder | `/homely/builder-defaults`, `/homely-meals/calculate`, `/create`, `/user/{id}`, `/search`, `/{id}` |
| AI coach | `POST /ai/coach`, `/ai/diet-plan`, `/ai/recipe-generator` |
| Settings | `GET/PUT /settings`, `GET/POST /search-history` |

(all paths are under `/api/v1`; the old paths in the contract's tables work too)

## 6. Live updates

The smart scale logs meals on its own, so the dashboard should update without a tap. Two options:
- **Simple:** poll `GET /user/daily-summary` every few seconds while the screen is visible.
- **Live:** `GET /user/stream` is Server-Sent Events: one `summary` event immediately, then one per change, plus `: ping` heartbeats every 15 s. It needs the `Authorization` header, so use an HTTP client (Dio with `ResponseType.stream`), not a browser `EventSource`. Reconnect with backoff if it ends.

## 7. Behaviours worth knowing

- **`source` on meals:** `esp32_yolo` / `esp32_qwen_vlm` (scale), `manual`, `fast_food`, `barcode`, `homely`, `recipe`, `ocr_label`. `llm-timeout` with 0 kcal means the scale's AI service was down at that moment.
- **AI answers carry `source`:** `gemini`, `local` (an on-premise model, shorter answers) or `offline` (canned text). Worth a subtle hint in the UI; never an error.
- **Days are UTC.** A meal logged shortly after midnight India time still counts toward the previous UTC day. Known limitation, a per-user timezone is planned.
- **Not built yet:** confirming/correcting the scale's guesses (HitL), push notifications, the agent chat, password-reset e-mail, token refresh.
- AI and image calls can take a few seconds (up to about 40 s in the worst case when two fallbacks are tried): use generous timeouts (60 s) and a spinner for `ai/*`, `ocr/upload`, `barcode/scan-image`.

## 8. Generating Dart models (optional)

```bash
npx @openapitools/openapi-generator-cli generate -i openapi_ms3.json -g dart-dio -o nutrix_api
```
Endpoints that return untyped JSON (coach, dashboard summary, history) appear as `Object`/`Map` there; model them by hand from the tables in `API_CONTRACT.md`.

## 9. What we need back from you

1. **Google sign-in:** the OAuth **client IDs** (web / Android / iOS) your app uses, so the backend can verify Google tokens (and the Android package name + SHA-1 if they are not registered yet).
2. A list (or the file) of the **API calls the current app makes**: base URL setting, and any call that does not send the `Authorization` header (those will get `401`).
3. Any endpoint you need that is missing, or any response field you need that is not there.
4. For each problem you report, include the **`X-Request-ID` response header** and the time: it lets us find that exact request in the backend logs.
