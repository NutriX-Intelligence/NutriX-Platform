# NutriX-MAS: A Proactive Multi-Agent System for Cognitive Healthcare Informatics

> **Track:** Agentic and Generative AI for Cognitive Healthcare Informatics
> **System:** NutriX — IoT-Integrated, Multi-Agent Dietary Intelligence Platform
> **Version:** 3.0 — Agentic Architecture Specification

---

## Abstract

NutriX is a smart dietary tracking ecosystem comprising an ESP32-S3 IoT scale with an OV2640 camera, a FastAPI microservice backend incorporating YOLOv8 computer vision and local Qwen/LLaMA inference, and a cross-platform Flutter application. This document formalizes the architectural upgrade from a reactive, request-driven pipeline into a **proactive, event-driven Multi-Agent System (MAS)** for precision clinical dietary informatics. The proposed framework introduces four co-operating agent tiers: a Tool-Executing Orchestrator Interface (Tier 1), an Autonomous Outlier Guardian (Tier 2A), a Multi-Agent Clinical MDT (Tier 2B), and an autonomic Meta-Auditor Agent capable of self-healing the inference pipeline without human developer intervention (Tier 3). The architecture explicitly addresses the hallucination risk inherent in generative models by wrapping stochastic LLM inference within deterministic physical solvers (Google OR-Tools LP), ICMR/FDA-grounded nutritional databases, and a formally defined Faithfulness Score ($S_{\text{faith}}$) that drives autonomous system remediation.

---

## 1. Research Formalization

### 1.1 Agent State Machine Definition

To establish academic rigor, every autonomous agent in the NutriX-MAS framework is formally defined as a tuple:

$$\mathcal{A} = \langle \mathcal{S},\ \mathcal{O},\ \mathcal{A}_c,\ \mathcal{T},\ \mathcal{R} \rangle$$

| Symbol | Formal Name | Instantiation in NutriX |
|---|---|---|
| $\mathcal{S}$ | State Space | Live Redis telemetry streams, PostgreSQL persistent records, raw ESP32-S3 sensor frames, and pipeline execution trace logs |
| $\mathcal{O}$ | Observation Function | Weight stabilization events (σ < 0.5g / 500ms), macro-threshold violation triggers from Redis, and inference faithfulness scores from execution traces |
| $\mathcal{A}_c$ | Action Space | REST API endpoint invocations, Google OR-Tools LP solver execution, `retrain_yolo.py` pipeline calls, LLM prompt patch commits, and PostgreSQL record mutations |
| $\mathcal{T}$ | State Transition | $S_{t+1} = \mathcal{T}(S_t, A_t)$ — deterministic for LP solver outputs; stochastic for LLM generation steps |
| $\mathcal{R}$ | Clinical Reward Signal | Minimization of macro-nutrient deviation $\Delta M$ and patient risk score $\rho$ over a 14-day rolling window |

### 1.2 Hybrid Deterministic-Stochastic Decision Engine

A core design principle of this architecture is the deliberate separation of stochastic and deterministic reasoning to mitigate clinical risk from generative AI hallucination:

- **Stochastic Layer:** Natural language comprehension (NL-to-SQL intent parsing), conversational coaching, and clinical rationale generation via local **Qwen2.5-7B-Instruct** or **LLaMA 3.1-8B** served through Ollama/vLLM.
- **Deterministic Layer:** Macro-constraint solving via **Google OR-Tools Linear Programming**, BMR/TDEE computation via the **Mifflin-St Jeor equation**, food identification via **YOLOv8** object detection, and string normalization via **RapidFuzz** (100+ Indian regional synonyms).

No clinical intervention recommendation is delivered without passing through the deterministic layer as a final constraint check.

### 1.3 Faithfulness Score and Self-Healing Trigger

The Tier 3 Meta-Auditor evaluates pipeline output quality using a weighted Faithfulness Score $S_{\text{faith}}$ computed against validated ground-truth databases (ICMR/USDA FoodData Central):

$$S_{\text{faith}} = \frac{\displaystyle\sum_{m \in \mathcal{M}} w_m \cdot \left(1 - \min\!\left(1,\ \frac{|M_{\text{pred}, m} - M_{\text{ground}, m}|}{M_{\text{ground}, m}}\right)\right)}{\displaystyle\sum_{m \in \mathcal{M}} w_m}$$

Where:
- $\mathcal{M} = \{\text{calories, protein, carbohydrates, fat}\}$ — the four macro-nutrient dimensions
- $w_m$ — clinical severity weight per macro (e.g., protein carries higher $w$ for post-surgical patients)
- $M_{\text{pred}}$ — model-generated macro estimate from the LLM Nutrition Service
- $M_{\text{ground}}$ — ground-truth value retrieved from the validated PostgreSQL food library

If $S_{\text{faith}} < \theta_{\text{heal}}$ (threshold configurable, default 0.70), the Meta-Auditor triggers autonomous remediation without human developer intervention.

### 1.4 Privacy and Edge Governance

Protected Health Information (PHI) and biometric data are subject to an **Edge-Filtered Privacy Protocol** enforced at the Flutter client layer. All conversational payloads are stripped of direct identifiers before leaving the local device network. Agent-to-agent communications are routed exclusively over the internal Docker network (no public internet exposure). PostgreSQL records are encrypted at rest; JWT-secured API boundaries prevent cross-user data leakage.

---

## 2. Complete System Architecture

### 2.1 Physical and Network Topology

```mermaid
flowchart TB
    subgraph EDGE["Edge Tier — IoT Hardware"]
        ESP["ESP32-S3 Smart Scale\nHX711 24-bit ADC\nOV2640 Camera Module"]
    end

    subgraph CLIENT["Client Tier — Flutter App"]
        APP["Flutter Mobile App\nAndroid ARM64 + Web\nRiverpod State Management"]
    end

    subgraph GATEWAY["API & Security Layer — Port 8000"]
        GW["FastAPI API Gateway\nJWT Auth + Device-Token\nRequest Routing"]
    end

    subgraph MS1["Microservice 1 — CV & Ingestion (Port 8001, GPU)"]
        YOLO["YOLOv8 Inference Engine\ncalcount_yolo_custom.pt\n123 Food Classes"]
        HITL["HitL Pipeline\n/dataset/pending/\n/dataset/trained/"]
        BARCODE["OpenCV Barcode Decoder\nOpenFoodFacts / USDA Fallback"]
    end

    subgraph MS2["Microservice 2 — LLM Nutrition (Port 8003, High-VRAM GPU)"]
        LLM["Qwen2.5-7B / LLaMA 3.1\nOllama (dev) / vLLM (prod)\nStructured JSON Output"]
    end

    subgraph MS3["Microservice 3 — Analytics (Port 8002, CPU)"]
        ANA["Redis Read-Only Service\n<10ms Response Latency"]
    end

    subgraph DATA["Data Layer"]
        PG[("PostgreSQL\nPermanent Storage\nFood Library + Meal Logs")]
        RD[("Redis\nLive Macro Streams\nReal-time Cache")]
    end

    subgraph MAS["Multi-Agent System Layer (Background Services)"]
        T1["Tier 1: Orchestrator Interface Agent"]
        T2A["Tier 2A: Outlier Guardian Agent"]
        T2B["Tier 2B: Clinical MDT Agents\n(Diagnostic · Intervention · Drafting)"]
        T3["Tier 3: Meta-Auditor Agent"]
    end

    ESP -->|"HTTP POST Multipart\nweight + JPEG + Device-Token"| GW
    APP -->|"HTTP GET/POST + JWT Bearer"| GW
    GW --> MS1
    GW --> MS3
    MS1 --> MS2
    MS1 --> PG
    MS2 --> PG
    PG -->|"Async Trigger: Recalculate Totals"| RD
    MS3 --> RD
    RD -->|"Live Stream Subscription"| T2A
    T1 --> PG
    T1 --> APP
    T2A -->|"Critical Outlier Event"| T2B
    T2B -->|"Clinical Report"| APP
    T3 -->|"Trace Log Polling"| MS1
    T3 -->|"Trace Log Polling"| MS2
    T3 -->|"Self-Heal Actions"| MS1
    T3 -->|"Self-Heal Actions"| MS2
```

### 2.2 Primary Ingestion Pipeline (Non-Agentic Baseline)

```mermaid
flowchart TD
    IN["Receive Multipart POST\nweight + JPEG + Device-Token"]
    BAR{"Barcode\nDetected?"}
    BCD["OpenCV Barcode Decode\n→ Extract Product Code"]
    YOLO["YOLOv8 Object Detection\ncalcount_yolo_custom.pt"]
    CONF{"Detection\nConfidence ≥ 80%?"}
    PEND["Save to /dataset/pending/\nFlag for HitL Review"]
    NOTIFY["Push Notification → Flutter App\n'Identify this item'"]
    PGDB{"Food in Local\nPostgreSQL?"}
    PGRET["Return Macros\nfrom Local DB"]
    EXTDB["Query OpenFoodFacts\nor USDA FoodData Central"]
    EXTFOUND{"Found in\nExternal DB?"}
    LLMCALL["POST /v1/llm/lookup\n→ LLM Nutrition Service\nQwen2.5-7B Structured Inference"]
    SAVE["INSERT record → PostgreSQL\nTrigger Redis Sync"]
    LOG["Append Execution Trace\nto Agent Audit Log"]

    IN --> BAR
    BAR -->|"Yes"| BCD --> PGDB
    BAR -->|"No"| YOLO --> CONF
    CONF -->|"≥ 80%"| PGDB
    CONF -->|"< 80%"| PEND --> NOTIFY
    PGDB -->|"Hit"| PGRET --> SAVE
    PGDB -->|"Miss"| EXTDB --> EXTFOUND
    EXTFOUND -->|"Found"| SAVE
    EXTFOUND -->|"Not Found"| LLMCALL --> SAVE
    SAVE --> LOG
```

---

## 3. Four-Tier Multi-Agent Architecture

### 3.1 Master Agent Workflow

```mermaid
flowchart TD
    subgraph T1BOX["Tier 1 — Orchestrator Interface Agent"]
        NL["User Natural Language Input\n(Voice or Text)"]
        INTENT["Intent Classification\n(LLM-powered Router)"]
        SQLGEN["NL-to-SQL Query Generator"]
        TOOLEX["Tool Execution Router\n(API Function Calls)"]
        MEALLOG["Auto-Meal Logger\nhomely_meals_engine.py"]
        RESPONSE["Structured Response\n→ Flutter App"]
        NL --> INTENT
        INTENT -->|"Data Query"| SQLGEN --> PG2[("PostgreSQL")]
        INTENT -->|"Meal Log"| MEALLOG --> PG2
        INTENT -->|"Tool Call"| TOOLEX
        TOOLEX --> RESPONSE
        PG2 --> RESPONSE
    end

    subgraph T2ABOX["Tier 2A — Outlier Guardian Agent (Async Background)"]
        STREAM[("Redis Live\nMacro Stream")]
        MONITOR["Stream Subscriber\n(Async Worker)"]
        THRESH{"Critical Threshold\nViolated?"}
        WARN["Level 1: Push Alert\n→ Flutter App"]
        ESCALATE["Level 2: Clinical Alert\nINSERT summary → PostgreSQL"]
        MDT_TRIGGER["Level 3: Trigger\nClinical MDT Handoff"]
        STREAM --> MONITOR --> THRESH
        THRESH -->|"Warning"| WARN
        THRESH -->|"Persistent Critical"| ESCALATE --> MDT_TRIGGER
    end

    subgraph T2BBOX["Tier 2B — Multi-Agent Clinical MDT"]
        DIAG["Diagnostic Agent\nAnalyse meal_logs, weight_logs\nNOVA processing flags, 14-day trends"]
        INTERV["Intervention Agent\nOR-Tools LP Solver\nMath-Optimal Corrective Meal Plan"]
        DRAFT["Drafting Agent\nGenerate Structured Clinical Report\nfor Dietitian Sign-Off"]
        DIAG --> INTERV --> DRAFT
    end

    subgraph T3BOX["Tier 3 — Meta-Auditor & Self-Healing Agent (Continuous)"]
        TRACES[("Pipeline Execution\nTrace Logs")]
        AUDIT["Meta-Auditor Agent\nEvaluate S_faith Scores"]
        FAIL{"Failure\nMode?"}
        YOLOHEAL["Auto-Annotate Images\n+ Trigger retrain_yolo.py"]
        LLMHEAL["Patch LLM System Prompt\nAppend Nutritional Constraints"]
        DBHEAL["Flag / Repair\nCorrupt DB Records"]
        TRACES --> AUDIT --> FAIL
        FAIL -->|"Low CV Confidence"| YOLOHEAL
        FAIL -->|"LLM Hallucination"| LLMHEAL
        FAIL -->|"Corrupt Record"| DBHEAL
    end

    MDT_TRIGGER --> DIAG
    DRAFT -->|"Report Delivered"| RD2[("Redis Stream")]
    YOLOHEAL --> RETRAIN["yolov8_retrained.pt\nUpdated Weights"]
    LLMHEAL --> PROMPT["Updated Prompt\nVersion in DB"]
```

---

## 4. Tier-by-Tier Deep Dive

### 4.1 Tier 1: Orchestrator Interface Agent

**Academic Role:** Tool-Executing Agent Interface — converts unstructured natural language into structured API parameters, positioning this as the agent that bridges the user's cognitive world and the system's computational world.

**Research Pitch:** *"A Tool-Executing Orchestrator Agent for Natural Language-Driven Dietary Database Interaction."*

```mermaid
sequenceDiagram
    actor User as User (Flutter App)
    participant T1 as Tier 1 Orchestrator Agent
    participant LLM as Local LLM Router
    participant DB as PostgreSQL
    participant ENG as Domain Engines

    User->>T1: "Log 2 katori dal and 1 tbsp ghee for dinner"
    T1->>LLM: classify_intent(utterance)
    LLM-->>T1: { intent: "meal_log", entities: [{ingredient: "dal", amount: 2, unit: "katori"}, ...] }
    T1->>ENG: homely_meals_engine.calculate(ingredients)
    ENG-->>T1: { kcal: 312, protein: 18g, carbs: 47g, fat: 6g }
    T1->>DB: INSERT INTO meal_logs ...
    DB-->>T1: { record_id: 9031 }
    T1-->>User: "Logged! Dal + ghee: 312 kcal, 18g protein. 620 kcal remaining today."
```

**Tool Registry (Function Calling Interface):**

| Tool Name | Underlying Engine | Trigger Pattern |
|---|---|---|
| `query_macros(food, weight)` | PostgreSQL → food_nutrients | "How many calories in X grams of Y?" |
| `log_meal(ingredients)` | homely_meals_engine.py | "Log [meal] for [meal_type]" |
| `get_daily_summary()` | Redis Analytics Service | "What have I eaten today?" |
| `recommend_recipes(goal)` | recipe_ranker.py | "What should I eat for dinner?" |
| `generate_meal_plan()` | optimization_engine.py (OR-Tools) | "Plan meals for the week" |
| `classify_diet(ingredients)` | classification_engine.py | "Is [product] vegan?" |

**Privacy Enforcement:** Before dispatching to any tool, the Tier 1 agent strips user PII from the canonical utterance. Database queries use parameterized `user_id` references — never raw email or name fields in query payloads.

---

### 4.2 Tier 2A: Autonomous Outlier Guardian Agent

**Academic Role:** Proactive, event-driven patient safety monitor that transforms NutriX from a passive logging tool into an autonomous guardian system.

**Research Pitch:** *"Event-Driven Autonomous Monitoring of Telemetric Dietary Outliers in High-Risk Patients."*

```mermaid
flowchart TD
    PG_TRIG["PostgreSQL Trigger\n(fires after every INSERT to meal_logs)"]
    REDIS_PUSH["Recalculate Running Totals\nPush to Redis Stream\nuser:{id}:macro_stream"]
    GUARDIAN["Tier 2A Guardian Agent\nAsync Redis Stream Subscriber\n(Background Worker)"]
    EVAL{"Threshold\nEvaluation"}

    GLYCEMIC{"Glycemic Risk?\n(Diabetic profile:\n>3 high-GI items in 60 min)"}
    PROTEIN{"Protein Deficit?\n(Post-surgical recovery:\n<30g by 18:00)"}
    CALORIC{"Severe Caloric\nExcess?\n(>130% TDEE)"}

    LVL1["Level 1 Alert\nFlutter Push Notification\nIn-app dietary warning"]
    LVL2["Level 2 Alert\nINSERT clinical_alerts → PostgreSQL\nClinician portal flag"]
    LVL3["Level 3 Escalation\nTrigger Tier 2B MDT Handoff\nFull diagnostic review"]

    PG_TRIG --> REDIS_PUSH --> GUARDIAN --> EVAL
    EVAL --> GLYCEMIC & PROTEIN & CALORIC
    GLYCEMIC -->|"Single occurrence"| LVL1
    GLYCEMIC -->|"Repeated (≥3 consecutive)"| LVL2
    CALORIC -->|"Single occurrence"| LVL1
    PROTEIN -->|"Persists beyond 18:00"| LVL2
    LVL2 -->|"No user correction within 24h"| LVL3
```

**Clinical Threshold Matrix:**

| Patient Profile | Monitored Signal | Warning Threshold (L1) | Critical Threshold (L2/L3) |
|---|---|---|---|
| Type 2 Diabetic | High-GI food count per 60-min window | ≥ 2 high-GI items | ≥ 3 high-GI items consecutively |
| Post-Surgical Recovery | Cumulative daily protein | < 40g by 18:00 | < 30g by 18:00 |
| Hypertensive | Daily sodium | > 2,000 mg | > 2,300 mg |
| Caloric Restriction | Daily calories vs. TDEE | > 115% | > 130% |
| Protein Goal | Daily protein vs. target | < 70% by 20:00 | < 50% by 20:00 |

**Design Rationale — Why Redis (Not PostgreSQL) for Monitoring:**
Polling PostgreSQL for every threshold check would create an additional 10–50ms read latency per event and couple the guardian's compute load to the primary write path. By subscribing to Redis streams (sub-millisecond reads), the Guardian Agent can evaluate 1,000+ dietary events per second without degrading the primary analytics API path.

---

### 4.3 Tier 2B: Multi-Agent Clinical MDT

**Academic Role:** Distributed cognitive workload across role-specialized sub-agents, mirroring hospital Multidisciplinary Team (MDT) structures where a neurologist, dietitian, and pharmacist each contribute specialized knowledge before a treatment plan is finalized.

**Research Pitch:** *"Multi-Agent Collaborative Reasoning for Precision Clinical Dietary Interventions."*

```mermaid
flowchart TD
    TRIGGER["MDT Trigger\n(from Tier 2A escalation\nor Clinician Manual Request)"]

    subgraph DIAG_BOX["Diagnostic Agent"]
        DIAG1["Load 30-day meal_logs\n(meal type, macros, timestamps)"]
        DIAG2["Scan weight_logs\n(trend analysis via adaptive_planner.py)"]
        DIAG3["Run classification_engine.py\n(NOVA processing levels 1-4\nVegan/Jain/Allergen flags)"]
        DIAG4["Compute Deficit Report\n(Δ macros vs. targets × 30 days)"]
        DIAG1 --> DIAG2 --> DIAG3 --> DIAG4
    end

    subgraph INTERV_BOX["Intervention Agent"]
        INT1["Receive Diagnostic Constraint Vector\n(Δ protein = +25g, Δ sodium = -800mg, ...)"]
        INT2["Invoke OR-Tools LP Solver\n(optimization_engine.py)\nMinimize macro deviation\nSubject to: dietary exclusions, budget, time"]
        INT3["Rank Corrective Recipes\n(recipe_ranker.py)\nBy: health_score × macro_fit × ingredient_coverage"]
        INT4["Output: Mathematically Optimal 4-Slot Plan\n(Breakfast / Lunch / Snack / Dinner)"]
        INT1 --> INT2 --> INT3 --> INT4
    end

    subgraph DRAFT_BOX["Drafting Agent"]
        DR1["Receive Optimal Plan + Diagnostic Summary"]
        DR2["Generate Clinical Report (LLM-drafted)\nSection A: Risk Findings\nSection B: Corrective Protocol\nSection C: Monitoring Targets"]
        DR3["Append Evidence Citations\n(ICMR threshold references\nNOVA processing level definitions)"]
        DR4["Submit for Clinician Sign-Off\nINSERT to clinical_reports table\nFlutter notification to dietitian portal"]
        DR1 --> DR2 --> DR3 --> DR4
    end

    TRIGGER --> DIAG1
    DIAG4 -->|"Constraint Vector"| INT1
    INT4 -->|"Optimal Plan"| DR1
```

**OR-Tools LP Formulation (Intervention Agent Core):**

The optimization problem solved by the Intervention Agent is formally stated as:

$$\text{Minimize} \quad \sum_{m \in \mathcal{M}} w_m \cdot \left| \sum_{r \in \mathcal{R}_{\text{plan}}} x_r \cdot M_{r,m} - T_m \right|$$

Subject to:
- $\sum_{r \in \mathcal{R}} x_r \leq 4$ — at most 4 meal slots per day
- $x_r \in \{0, 1\}$ — binary selection per recipe $r$
- $M_{r,m}$ — macro $m$ per serving of recipe $r$ (from recipe_nutrition table)
- $T_m$ — corrective macro target for dimension $m$ (from Diagnostic Agent)
- Exclusion constraints: $x_r = 0$ if recipe $r$ violates any dietary rule in `ingredient_rules`

---

### 4.4 Tier 3: Meta-Auditor and Self-Healing Agent

**Academic Role:** The meta-level autonomic controller that monitors the system's own inference quality. Operates completely independently of user-facing flows and requires no human developer intervention to execute remediation.

**Research Pitch:** *"A Self-Auditing, Meta-Agentic Pipeline for Automated Quality Assurance in Nutritional Computer Vision."*

```mermaid
sequenceDiagram
    participant CV as CV & Ingestion Service
    participant LLM as LLM Nutrition Service
    participant LOG as Execution Trace Log (PostgreSQL)
    participant AUD as Tier 3 Meta-Auditor Agent
    participant DB as Ground Truth DB (ICMR / USDA)
    participant YOLO as YOLOv8 Retrain Pipeline
    participant PROMPT as LLM Prompt Registry

    CV->>LOG: Append trace { food_id, confidence: 0.42, source: "yolo" }
    LLM->>LOG: Append trace { food_name: "apple", fat_pred: 89g, source: "llm" }

    loop Every 15 minutes
        AUD->>LOG: Pull all traces since last_audit_timestamp
        AUD->>DB: Retrieve ground truth macros for logged foods
        AUD->>AUD: Compute S_faith per trace
        
        alt S_faith < 0.70 AND source = "llm"
            AUD->>PROMPT: Append constraint rule to system prompt
            Note over PROMPT: "apple fat < 1g per 100g — verified ICMR"
            AUD->>DB: Flag corrupt record for manual review
        else S_faith OK but CV confidence < 0.80 (recurring for same food)
            AUD->>LOG: Pull /dataset/pending/ images for food class
            AUD->>YOLO: Trigger retrain_yolo.py (3-epoch fine-tune)
            Note over YOLO: Saves updated weights → yolov8_retrained.pt
        else All traces pass
            AUD->>LOG: Write audit_passed = true for batch
        end
    end
```

**Faithfulness Score Computation — Detailed Pipeline:**

```mermaid
flowchart TD
    TRACE["Raw Execution Trace\n{ food_name, source, predicted_macros, confidence }"]
    GT["Ground Truth Lookup\nPostgreSQL food_nutrients table\n(ICMR / USDA validated)"]
    COMP["Compute Per-Macro Deviation\nΔ_m = |M_pred - M_ground| / M_ground"]
    WEIGHT["Apply Clinical Weights\nProtein: w=0.35 | Calories: w=0.30\nCarbs: w=0.20 | Fat: w=0.15"]
    SCORE["S_faith = Σ(w_m × (1 - min(1, Δ_m))) / Σ(w_m)"]
    THRESH{"S_faith\n≥ 0.70?"}
    PASS["Mark trace PASS\nLog audit_passed = true"]
    FAIL_CLASS["Classify Failure Mode"]
    LLM_FAIL["LLM Hallucination\n(source = llm AND S_faith < 0.70)"]
    CV_FAIL["CV Misidentification\n(source = yolo AND confidence < 0.80)"]
    DB_FAIL["Database Error\n(ground truth lookup failed)"]
    ACT_LLM["Patch LLM System Prompt\nAppend validated nutritional constraint"]
    ACT_CV["Trigger 3-Epoch YOLOv8 Fine-Tune\nmove images pending → trained"]
    ACT_DB["Flag Record in PostgreSQL\nInsert to audit_flags table"]

    TRACE --> GT --> COMP --> WEIGHT --> SCORE --> THRESH
    THRESH -->|"Pass"| PASS
    THRESH -->|"Fail"| FAIL_CLASS
    FAIL_CLASS --> LLM_FAIL --> ACT_LLM
    FAIL_CLASS --> CV_FAIL --> ACT_CV
    FAIL_CLASS --> DB_FAIL --> ACT_DB
```

**Self-Healing Action Taxonomy:**

| Failure Mode | Detection Signal | Autonomous Remediation | Escalation Condition |
|---|---|---|---|
| **LLM Hallucination** | $S_{\text{faith}} < 0.70$ AND `source = "llm"` | Append validated constraint to system prompt registry | > 5 consecutive failures for same food class |
| **YOLOv8 Class Drift** | Confidence < 0.80 recurring ≥ 3× for same food class | Move `/dataset/pending/` images → `/dataset/trained/`, trigger `retrain_yolo.py` (3 epochs) | Accuracy < 0.70 post-retrain |
| **Corrupt DB Record** | Ground truth lookup returns NULL or physiologically implausible value (e.g., fat > 100g/100g) | Flag record in `audit_flags` table, remove from live lookup cache | Developer alert via monitoring dashboard |
| **OCR Extraction Error** | Extracted macro sum ≠ 100g ± tolerance | Discard OCR result, fall through to LLM Vision fallback | Gemini Vision API also fails |

---

## 5. End-to-End Agentic Workflow Traces

### Trace A: Autonomous Glycemic Alert → MDT Clinical Report

```mermaid
sequenceDiagram
    actor Scale as ESP32-S3 Scale
    participant GW as API Gateway
    participant CV as CV & Ingestion (MS1)
    participant PG as PostgreSQL
    participant RD as Redis Stream
    participant T2A as Tier 2A Guardian
    participant T2B as Tier 2B MDT
    participant App as Flutter App
    actor Diet as Dietitian

    Scale->>GW: POST /v1/ingest/weight-frame { weight: 145g, image: JPEG }
    GW->>CV: Route to CV Service
    CV->>CV: YOLOv8 → "gulab_jamun" at 91% confidence
    CV->>PG: INSERT meal_log { user_id: 101, food: "gulab_jamun", kcal: 387 }
    PG->>PG: Trigger: recalculate user_101 totals
    PG->>RD: XADD user:101:macro_stream { sugar: 89g, kcal_total: 1840 }
    
    Note over T2A: Async subscriber fires instantly
    T2A->>RD: XREAD user:101:macro_stream (latest)
    T2A->>T2A: Evaluate: diabetic profile, 3rd high-GI item in 45 min
    T2A->>App: Level 2 Alert: "Critical glycemic risk detected"
    T2A->>PG: INSERT clinical_alerts { severity: CRITICAL, user_id: 101 }
    
    Note over T2A: 24h passes — no user dietary correction
    T2A->>T2B: Trigger MDT Handoff { user_id: 101, alert_id: 772 }
    
    T2B->>PG: Diagnostic Agent pulls 30-day meal_logs, weight_logs
    T2B->>T2B: Intervention Agent runs OR-Tools LP → low-GI meal plan
    T2B->>T2B: Drafting Agent generates structured clinical report
    T2B->>Diet: INSERT clinical_report → dietitian portal notification
    Diet->>App: Approve & send corrective plan to patient
```

### Trace B: Meta-Auditor Detects LLM Hallucination → Self-Heal

```mermaid
sequenceDiagram
    participant LLM as LLM Nutrition Service
    participant LOG as Trace Log
    participant AUD as Tier 3 Meta-Auditor
    participant DB as ICMR/USDA Ground Truth
    participant PROMPT as System Prompt Registry

    LLM->>LOG: Append { food: "apple", fat_pred: 89.3g, source: "llm" }
    
    Note over AUD: Scheduled audit cycle fires (15 min)
    AUD->>LOG: Pull traces since last_audit_ts
    AUD->>DB: Lookup { food: "apple" } → { fat_ground: 0.2g/100g }
    AUD->>AUD: Δ_fat = |89.3 - 0.2| / 0.2 = 445.5 → capped at 1.0
    AUD->>AUD: S_faith = 0.15 × (1 - 1.0) + ... = 0.21 → FAIL
    AUD->>PROMPT: APPEND constraint: "apple: fat content must be < 1g per 100g"
    AUD->>LOG: INSERT audit_flag { trace_id: X, action: "prompt_patched", severity: HIGH }
    
    Note over PROMPT: Next LLM call for "apple" uses patched prompt
    LLM->>LOG: Append { food: "apple", fat_pred: 0.3g, source: "llm" }
    AUD->>AUD: S_faith = 0.94 → PASS
```

---

## 6. Comparative Analysis: Reactive vs. Proactive Architecture

| Dimension | Reactive NutriX (v2.0) | Proactive NutriX-MAS (v3.0) |
|---|---|---|
| **Patient Safety** | User manually reviews their own data | Guardian Agent detects critical dietary shifts in real time, < 1s latency |
| **Clinical Workflow** | No clinical staff integration | Autonomous MDT report generation with dietitian sign-off portal |
| **Model Quality** | Model degrades silently; requires developer intervention | Meta-Auditor detects drift and self-heals within a 15-minute audit cycle |
| **Hallucination Risk** | LLM output unchecked | Every LLM output evaluated against ICMR/USDA ground truth via $S_{\text{faith}}$ |
| **User Interaction** | Explicit manual logging required | Orchestrator Agent converts natural language to structured DB operations |
| **System Resilience** | Single point of failure per microservice | Autonomous remediation; failing components patched without downtime |
| **Research Contribution** | Applied ML system | Novel MAS with formal agent definitions, event-driven safety protocol, and autonomic self-healing |

---

## 7. Agent Communication and Data Flow Matrix

```mermaid
flowchart TB
    subgraph INPUTS["External Inputs"]
        ESP2["ESP32-S3 Scale\nHTTP POST Multipart"]
        USER2["User NL Input\nFlutter App"]
    end

    subgraph PIPELINE["Ingestion Pipeline"]
        GW2["API Gateway\n:8000"]
        MS12["CV & Ingestion\n:8001"]
        MS22["LLM Nutrition\n:8003"]
        MS32["Analytics\n:8002"]
    end

    subgraph STORAGE["Shared Data Stores"]
        PG2[("PostgreSQL")]
        RD2[("Redis Stream")]
        LOG2[("Audit Trace Log")]
    end

    subgraph AGENTS["Agent Layer (Background Services)"]
        A1["T1: Orchestrator\nFunction Calls + NL-to-SQL"]
        A2["T2A: Guardian\nRedis Subscriber"]
        A3["T2B: MDT\nDiag → Interv → Draft"]
        A4["T3: Auditor\nS_faith + Self-Heal"]
    end

    subgraph OUTPUTS["Outputs"]
        ALERT["Clinical Alert\nFlutter Push"]
        REPORT["Clinical Report\nDietitian Portal"]
        WEIGHTS["Updated Model\nyolov8_retrained.pt"]
        PROMPT2["Patched Prompt\nLLM Registry"]
    end

    ESP2 --> GW2
    USER2 --> A1
    GW2 --> MS12 --> PG2 & LOG2
    MS12 --> MS22 --> PG2 & LOG2
    PG2 --> RD2
    MS32 --> RD2
    RD2 --> A2
    A2 -->|"Outlier Event"| A3
    A3 --> REPORT
    A2 --> ALERT
    A1 --> PG2
    A4 --> LOG2
    A4 --> WEIGHTS
    A4 --> PROMPT2
    MS12 --> LOG2
    MS22 --> LOG2
```

---

## 8. Technology Stack — Agentic Extension

| Component | Technology | Purpose |
|---|---|---|
| **Agent Orchestration** | Python `asyncio` + FastAPI Background Tasks | Non-blocking concurrent agent execution |
| **LLM Inference (Agents)** | Qwen2.5-7B-Instruct via Ollama / vLLM | Intent classification, NL-to-SQL, clinical drafting |
| **Stream Processing** | Redis Streams (`XADD` / `XREAD`) | Sub-millisecond live macro event delivery to Guardian Agent |
| **Constraint Solving** | Google OR-Tools (Linear Programming) | Mathematically optimal corrective meal plan generation |
| **Computer Vision** | Ultralytics YOLOv8 | Food object detection (123 classes, 80% confidence threshold) |
| **Self-Healing Trigger** | `subprocess` → `retrain_yolo.py` | Autonomous 3-epoch fine-tuning on HitL-corrected data |
| **Audit Storage** | PostgreSQL `audit_logs` + `audit_flags` tables | Persistent trace log for faithfulness scoring and failure forensics |
| **Clinical Output** | PostgreSQL `clinical_reports` table | Structured MDT reports with dietitian sign-off workflow |
| **Privacy Layer** | Flutter Secure Storage + JWT | PHI stripping at client edge; parameterized DB queries |
| **Fuzzy NLP** | RapidFuzz (100+ Indian synonym map) | Regional dietary term normalization for NL-to-SQL queries |

---

## 9. Novel Academic Contributions

| Contribution | Description | Research Track Alignment |
|---|---|---|
| **Autonomic Self-Healing Pipeline** | $S_{\text{faith}}$ metric drives zero-human-intervention model remediation | AI-powered hospital resource management; Secure health AI |
| **Event-Driven Guardian Agent** | Redis stream subscription for sub-second dietary anomaly detection | Autonomous patient monitoring systems |
| **Role-Specialized MDT Simulation** | Three sub-agents (Diagnostic, Intervention, Drafting) mirror clinical team structures | Clinical decision-support agents; Digital health twins |
| **Deterministic-Stochastic Hybrid** | OR-Tools LP solver as a hard safety wrapper around stochastic LLM outputs | Trustworthy AI in healthcare |
| **IoT-Native Agent Perception** | ESP32-S3 hardware telemetry directly feeds agent state transitions | Edge AI and connected health infrastructure |
| **NL-Tool-Execution Interface** | Orchestrator converts conversational input to typed API calls without manual form filling | Human-AI interaction for clinical workflows |

---

## 10. Deployment and Containerization

```mermaid
flowchart TB
    subgraph PUBLIC["Public Internet"]
        ESP3["ESP32-S3 Scale"]
        APP3["Flutter App"]
    end

    subgraph DOCKER["Docker Compose Network (Internal)"]
        GW3["gateway :8000\n(Public port only)"]

        subgraph GPU_A["GPU Node A — Fast Inference"]
            CV3["cv-ingestion :8001"]
        end
        subgraph GPU_B["GPU Node B — High VRAM"]
            LLM3["llm-nutrition :8003\nOllama / vLLM"]
        end
        subgraph CPU["CPU Nodes"]
            ANA3["analytics :8002"]
            AGT["agent-services :8004\n(T1 + T2A + T2B + T3)"]
        end
        subgraph DATA3["Data Layer"]
            PG3["postgres :5432"]
            RD3["redis :6379"]
        end
    end

    ESP3 & APP3 -->|"Port 8000 only"| GW3
    GW3 --> CV3
    GW3 --> ANA3
    CV3 --> LLM3
    CV3 & LLM3 --> PG3
    PG3 --> RD3
    ANA3 & AGT --> RD3
    AGT --> PG3
    CV3 & LLM3 -->|"Execution traces"| AGT
```

> [!NOTE]
> All four agent tiers run as asynchronous background tasks within a dedicated `agent-services` container. The Guardian Agent (T2A) runs as a persistent `asyncio` event loop. The Meta-Auditor (T3) is scheduled as a recurring task (every 15 minutes). Tiers 1 and 2B are invoked on-demand.

> [!IMPORTANT]
> Only **Port 8000** (API Gateway) is exposed to the public internet. The agent service layer (Port 8004), database ports (5432, 6379), and inference service ports (8001, 8003) are exclusively accessible within the Docker internal network — a critical security boundary for PHI protection.
