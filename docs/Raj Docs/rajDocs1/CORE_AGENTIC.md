# WACV 2027 Technical Audit: Core Agentic & LLM System

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Multi-Agent Architecture, LLM Integrations, Explanation Engines, System Prompt Registries, and Clinical Guardian Audit Logs.

---

## 1. Executive Summary & Status Classification

| Agent / LLM Component | Primary File Location | Implementation Status | Evidence / Code References |
| :--- | :--- | :--- | :--- |
| **Gemini AI Structured Vision/Barcode Engine** | [app/services/barcode_service.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/barcode_service.py#L58-L119) | `[CORE IMPLEMENTED]` | Multi-model fallback (`gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-2.5-flash`, `gemini-1.5-pro`) with strict JSON output parsing for per-100g macro estimation. |
| **Deterministic Rule-Based Explanation Engine** | [app/services/explanation_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/explanation_engine.py#L1-L162) | `[CORE IMPLEMENTED]` | Zero-latency, rule-based explanation generator producing structured summaries, bullet points, and goal suitability notes without external API latency. |
| **LLM & RAG Microservice Container (MS2)** | [ms2_llm/main.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms2_llm/main.py) | `[PARTIAL]` | FastAPI microservice container initialized with database health check and Redis caching hooks. |
| **Clinical Guardian & Agent Engine (MS4)** | [ms4_agents/main.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms4_agents/main.py) | `[PARTIAL]` | FastAPI microservice container initialized with health check hooks. |
| **System Prompt Registry & Meta-Auditor Schema** | [shared/models.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/shared/models.py#L601-L686) | `[CORE IMPLEMENTED]` | Database tables `SystemPromptRegistry`, `AuditLog`, `ClinicalAlert`, `ClinicalReport` for versioning prompts and logging faithfulness scores (`s_faith_score`). |

---

## 2. Gemini AI Integration Details

The repository incorporates Google Gemini API calls as a Tier 3 fallback inside `BarcodeService.estimate_nutrition_from_gemini()`:

* **Trigger Condition:** Used when Open Food Facts API lacks full nutritional details for a scanned packaged food item.
* **Target Models:** Iterates through `gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-2.5-flash`, and `gemini-1.5-pro`.
* **Structured Output Guarantee:** Employs explicit prompt engineering instructing the model to output raw JSON without markdown formatting:
  ```json
  {
    "energy_kcal": 420.0,
    "protein_g": 6.5,
    "carb_g": 64.0,
    "fat_g": 18.0,
    "fibre_g": 2.5,
    "sodium_mg": 700.0,
    "sugar_g": 4.0,
    "saturated_fat_g": 7.5,
    "brand": "Brand Name",
    "ingredients_text": "Corn meal, edible vegetable oil..."
  }
  ```
* **Validation Guard:** Checks results against `is_valid_nutrients()` to reject zero-value or corrupted outputs.

---

## 3. Explanation Engine (`ExplanationEngine`)

To ensure real-time user responsiveness and avoid LLM hallucinations, `ExplanationEngine` provides deterministic rationale for recipe recommendations based on:
1. **Dietary Classification:** Jain (no onion/garlic/root veg), Vegan, Vegetarian, Eggetarian, Non-Vegetarian.
2. **Ingredient Match Quality:** Reports percentage and count of matched vs. required ingredients.
3. **Health Score Interpretation:** Maps health score $[0, 100]$ to visual indicators (🥗 Excellent, ⚖️ Moderate, ⚠️ Caution).
4. **Macro Highlights:** Detects high-protein ($\ge 15\text{g}/100\text{g}$), low-calorie ($< 100\text{ kcal}/100\text{g}$), low-carb ($< 10\text{g}/100\text{g}$), and low-fat ($< 5\text{g}/100\text{g}$).
5. **Goal Suitability:** Evaluates alignment with fat loss, muscle gain, or maintenance.

---

## 4. Agentic Database Architecture & Prompt Versioning

In [shared/models.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/shared/models.py):

1. **`SystemPromptRegistry`:** Stores prompt versioning, active status, and track of whether prompts were patched by human developers or the automated `meta_auditor`.
2. **`AuditLog`:** Tracks all inference calls (`yolo_inference`, `llm_lookup`, `llm_vision`, `agent_query`), latency in milliseconds, confidence, output hashes, and meta-auditor faithfulness score (`s_faith_score`).
3. **`ClinicalAlert` & `ClinicalReport`:** Stores clinical alert triggers across 3 severity levels (`L1_notification`, `L2_logged`, `L3_mdt_triggered`) and Multi-Disciplinary Team clinical reports.
