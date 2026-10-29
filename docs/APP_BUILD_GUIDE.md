# Updating the NutriX Flutter app to the new backend: build guide

Read `APP_HANDOFF.md` first (backend address, test login, first run). This guide is the work plan: what to change in the app, in what order, with the code for the parts that are easy to get wrong. It assumes the stack described for the app: Flutter 3.x, Riverpod, Dio, `flutter_secure_storage`, `google_sign_in`.

The backend is **backward compatible**: the old paths still answer, so you can migrate screen by screen and always have a working app. Only two things are not optional: the login token is now **required on every call**, and old tokens no longer work (everyone signs in once).

---

## 0. Rules to build by
1. **One networking class** talks to the backend. No screen builds URLs or headers itself.
2. **Base URL comes from build config**, never from code: `--dart-define=API_BASE_URL=https://...` (one value per environment/flavor).
3. **Token on every request** (except register / login / google / reset-password), stored in secure storage.
4. **`401` = sign out and show login.** `403` = a bug in the app (it sent another user's id).
5. **Let the server decide "today".** For "now" actions leave the date out: no `log_date` when creating a meal/water/weight log, and no `log_date` / `date` parameter when reading today's meals (`/meal-logs/today/{id}`) or `daily-summary`. The server uses one clock (India time) for both, so they can never disagree. Send an explicit `YYYY-MM-DD` only for a different day (calendar, history, backdating), taken from the date the user picked. **Never** build "today" on the device with `DateTime.now()` or `.toUtc()` for these calls: mixing the two is exactly what makes a just-logged meal vanish from the today screen after midnight. Units are grams/kcal/ml.
6. Use generous timeouts for AI and image calls (60 s).

## 1. The networking layer (do this first)

```dart
// lib/core/api/api_client.dart
import 'package:dio/dio.dart';

const apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000'); // emulator -> your PC

class ApiClient {
  ApiClient({required this.tokenStore, this.onUnauthorized})
      : dio = Dio(BaseOptions(
          baseUrl: apiBaseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
          headers: {'Accept': 'application/json'},
        )) {
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await tokenStore.read();
        if (token != null && !_isPublic(options.path)) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (e, handler) async {
        final path = e.requestOptions.path;
        if (e.response?.statusCode == 401 && !_isPublic(path)) {
          await tokenStore.clear();      // expired / invalid / unknown user
          onUnauthorized?.call();        // navigate to the login screen
        }
        handler.next(e);
      },
    ));
  }

  final Dio dio;
  final TokenStore tokenStore;
  final void Function()? onUnauthorized;

  // a wrong password also returns 401: never treat those as "session expired"
  static bool _isPublic(String path) => RegExp(r'/auth/(register|login|google|reset-password)$').hasMatch(path);
}

// lib/core/api/token_store.dart
class TokenStore {
  final _storage = const FlutterSecureStorage();
  Future<String?> read() => _storage.read(key: 'access_token');
  Future<void> write(String t) => _storage.write(key: 'access_token', value: t);
  Future<void> clear() => _storage.delete(key: 'access_token');
}
```

Turn errors into messages once:
```dart
String apiErrorMessage(Object e) {
  if (e is DioException) {
    final d = e.response?.data;
    if (d is Map && d['detail'] is String) return d['detail'] as String;              // 400/401/403/404/503
    if (d is Map && d['detail'] is List && (d['detail'] as List).isNotEmpty) {         // 422 validation
      return ((d['detail'] as List).first as Map)['msg']?.toString() ?? 'Invalid input';
    }
    if (e.type == DioExceptionType.connectionError) return 'Cannot reach the server';
  }
  return 'Something went wrong';
}
```

Expose it with Riverpod (`final apiClientProvider = Provider((ref) => ApiClient(tokenStore: TokenStore(), onUnauthorized: ...));`) and build one **repository per area** on top (`AuthRepository`, `DashboardRepository`, `MealRepository`, `RecipeRepository`, `ScanRepository`, `CoachRepository`...). Screens only talk to repositories/providers.

## 2. Models
Generate the DTOs from `openapi_ms3.json` (see `APP_HANDOFF.md` §8), then hand-write the few untyped ones from `API_CONTRACT.md`: `DailySummary`, `HistoryPage`, `CoachReply`. Keep every field nullable that the contract marks optional.

## 3. Staged migration (each stage ends with something you can demo)

| Stage | Work | Done when |
|---|---|---|
| **A. Connect** | `ApiClient`, base URL via `--dart-define`, `GET /health/all` from a debug screen | the app reaches the backend on device + emulator |
| **B. Auth** | login / register / Google / logout; store token; route guard using `GET /api/v1/auth/me`; `is_onboarded == false` -> onboarding -> `POST /api/v1/user/profile` | test account signs in; a wrong password shows a message (not "session expired"); killing the token forces login |
| **C. Dashboard** | rings from `GET /api/v1/user/daily-summary`; diary list from `GET /api/v1/user/history` | numbers match `curl`; a scale scan or manual log shows after refresh |
| **D. Logging** | manual meal / water / weight create + delete (`/meal-logs`, `/water-logs`, `/weight-logs`) | add and delete a meal and the rings change |
| **E. Scan** | barcode number, barcode photo, label photo (multipart, see below); manual barcode; alternatives | each returns a product card; slow calls show a spinner |
| **F. Food discovery** | fast food, recipes (top/search/detail/recommend/filter), meal plan, homely builder | lists load; filters respect the user's diet |
| **G. AI** | coach (with history), diet plan, recipe generator, recipe instructions | answers render; show a small badge when `source != "gemini"` |
| **H. Live** | `GET /api/v1/user/stream` on the dashboard | a meal logged elsewhere updates the rings within a second |
| **I. Clean-up** | replace the last legacy paths (table in §5), remove dead code | no request in the backend log uses an unprefixed path |

## 4. Code you will need

**Login and token**
```dart
Future<User> login(String email, String password) async {
  final r = await dio.post('/api/v1/auth/login', data: {'email': email, 'password': password});
  await tokenStore.write(r.data['access_token'] as String);
  return User.fromJson(r.data['user']);
}
```

**Google sign-in** (the server needs the *ID token*; on Android set `serverClientId` to the **web** client id)
```dart
final account = await GoogleSignIn(scopes: ['email'], serverClientId: kWebClientId).signIn();
final idToken = (await account!.authentication).idToken;
final r = await dio.post('/api/v1/auth/google', data: {'id_token': idToken});   // same response shape as login
```

**Image upload** (`http_parser` for `MediaType`)
```dart
Future<Map<String, dynamic>> scanBarcodePhoto(String path, {String? diet}) async {
  final form = FormData.fromMap({
    'file': await MultipartFile.fromFile(path, filename: 'barcode.jpg', contentType: MediaType('image', 'jpeg')),
    if (diet != null) 'diet_type': diet,        // never send a user_id: the server uses the token
  });
  final r = await dio.post('/api/v1/barcode/scan-image', data: form,
      options: Options(receiveTimeout: const Duration(seconds: 60)));
  return r.data as Map<String, dynamic>;
}
// label photo: POST /api/v1/ocr/upload, same form (field "file"; optional meal_type + food_name logs it)
```

**Live dashboard stream (SSE)**
```dart
Stream<DailySummary> summaryStream() async* {
  final res = await dio.get<ResponseBody>('/api/v1/user/stream',
      options: Options(responseType: ResponseType.stream, receiveTimeout: Duration.zero,
          headers: {'Accept': 'text/event-stream'}));
  String? event;
  await for (final line in utf8.decoder.bind(res.data!.stream.cast<List<int>>()).transform(const LineSplitter())) {
    if (line.startsWith('event:')) {
      event = line.substring(6).trim();
    } else if (line.startsWith('data:') && event == 'summary') {
      yield DailySummary.fromJson(jsonDecode(line.substring(5)) as Map<String, dynamic>);
    } else if (line.isEmpty) {
      event = null;                 // frame boundary; lines starting with ':' are heartbeats: ignore
    }
  }
}
```
Wrap it in a Riverpod `StreamProvider` that reconnects with a short back-off when it ends, and cancel it when the dashboard is not visible. If anything about SSE is awkward, polling `daily-summary` every 3 to 5 s is an acceptable fallback.

**Dates:** omit the date for today (rule 5); send `YYYY-MM-DD` only for a day the user picked. Never let one screen compute its own "today". **Never send a user id the user does not own:** use the id from `auth/me` (or omit it where the contract says the server derives it).

## 5. Old path -> new path (find-and-replace list)
Rule of thumb: `/api/<x>` becomes `/api/v1/<x>`; an unprefixed `/<x>` becomes `/api/v1/<x>`. The exceptions:

| Old | New |
|---|---|
| `/calculate-profile` | `/api/v1/user/profile` |
| `/recommend-foods` | `/api/v1/foods/recommend` |
| `/generate-meal-plan` | `/api/v1/meal-plans/generate` |
| `/track-weight` | `/api/v1/weight-logs` |
| `/api/ocr` | `/api/v1/ocr/upload` |
| `/users/{id}/targets` | `/api/v1/user/targets` (no id) or `/api/v1/users/{id}/targets` |
| everything else (`/api/auth/*`, `/api/meal-logs...`, `/api/water-logs...`, `/api/weight-logs/{id}`, `/api/analytics/...`, `/api/fast-food/...`, `/api/barcode/...`, `/api/classify...`, `/api/homely...`, `/api/ai/...`, `/api/recipes/generate-instructions`, `/api/settings`, `/api/search-history`, `/recipes/...`, `/users/{id}/weight-history`, `/users/{id}/meal-plans`) | same path with `/api/v1` in front (drop a leading `/api` first) |

**Removed on purpose** (do not call): `GET /users/{email}` (use `GET /api/v1/auth/me`), `POST /recipes/train-ml`.

## 6. UI details the backend now supports
- **Meal source icon/label** from `source`: `esp32_yolo` / `esp32_qwen_vlm` (smart scale), `manual`, `fast_food`, `barcode`, `homely`, `recipe`, `ocr_label`. `llm-timeout` with 0 kcal = the scale's AI was down: show it as "could not identify", not "0 kcal food".
- **Browse Recipes must page.** `POST /foods/recommend` returns one page (default 300). Read `X-Total-Count` / `X-Has-More` from the response headers and load more as the user scrolls (`offset += limit`). For the "All" tab send `exclude_fast_food: true` (fast food has its own chip), otherwise fast-food items fill part of each page and are then hidden by the UI, which is how a Jain user saw only 36 recipes. The reported counts were 60 per page minus the hidden fast-food items.
- **AI text fields are strings.** `reply` (coach), `plan` (diet plan), `recipe` and `instructions` are Markdown **strings**; casting any of them to `List` throws `type 'String' is not a subtype of type 'List<dynamic>'`. Show them in a Markdown widget (for example `flutter_markdown`). For a structured meal list use `/meal-plans/generate`.
- **"Log this recipe" (AI recipe generator):** pre-fill the dialog from the response fields `name` and `nutrition.calories / protein_g / carbs_g / fat_g` (per serving). Never regex the Markdown text for numbers. A `null` field means "unknown": show an empty input, not `0`. If `nutrition.consistent == false`, the calories do not match the macros: show a small "check these numbers" hint.
- **AI badge:** `source: "local"` or `"offline"` on coach / plan / recipe answers: a small "limited mode" hint; never an error dialog.
- **Diary and rings share one source of truth:** after any create/delete, re-fetch `daily-summary` (or rely on the stream).
- **Onboarding:** drive it from `is_onboarded`, not from local flags.

## 7. Testing
- Run every stage against the real backend with the test account; keep a small integration test per repository (login, daily summary, add + delete a meal).
- Verify the failure paths on purpose: wrong password, expired/garbage token (`401` -> login), backend down (friendly message), AI slow (spinner, no timeout crash).
- When something looks wrong, note the response's **`X-Request-ID`** and the time and send them to the backend owner.

## 8. Definition of done
- [ ] Base URL set per environment with `--dart-define`; no hard-coded hosts.
- [ ] Register, login, Google, logout, onboarding all work; `401` always lands on login.
- [ ] Dashboard (rings + diary) correct and live-updating; a scale scan appears without user action.
- [ ] Manual log/delete for meals, water and weight.
- [ ] Barcode number, barcode photo, label photo, alternatives.
- [ ] Fast food, recipes, meal plan, homely builder, AI coach/plan/recipe.
- [ ] No unprefixed legacy path is still used; no call sends another user's id.
- [ ] Android release build works over HTTPS (no cleartext flag needed).
