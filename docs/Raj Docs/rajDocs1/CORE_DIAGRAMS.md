# WACV 2027 Technical Audit: Diagram & Architecture Inventory

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Architectural Diagrams, Mermaid Flowcharts, Sequence Diagrams, ER Models, and Training Output Plots.

---

## 1. System Architecture Diagrams Inventory

| Diagram Path | Diagram Type | Technical Contents & Description | Technical Accuracy | WACV Paper Relevance |
| :--- | :--- | :--- | :--- | :--- |
| **[docs/ArchitectureDiagrams.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/ArchitectureDiagrams.md#L7-L69)** | Mermaid Graph (`graph TD`) | **High-Level System Architecture:** Client Layer (SPA, Mobile Web) $\rightarrow$ API & Security Gateway (FastAPI, JWT, Pydantic) $\rightarrow$ 14 Intelligence Engines $\rightarrow$ Database Layer (PostgreSQL/SQLite, Fuzzy Index) $\rightarrow$ External Services (Open Food Facts, DuckDuckGo, Gemini AI). | **Accurate:** Exactly reflects the microservice breakdown and fallback tiers. | **High (Fig 1 candidate):** Core system architecture diagram for WACV System/Applications section. |
| **[docs/ArchitectureDiagrams.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/ArchitectureDiagrams.md#L76-L100)** | Mermaid Graph (`graph LR`) | **Tech Stack Inventory:** Maps Backend (Python 3.10, FastAPI, SQLAlchemy), AI/ML (Google OR-Tools, RapidFuzz, scikit-learn, XGBoost, Gemini), Frontend (Vanilla JS, CSS, Chart.js). | **Accurate:** Matches `requirements.txt` dependencies across all microservices. | **Medium:** Useful for technical appendix. |
| **[docs/MASTER_ARCHITECTURE.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/docs/MASTER_ARCHITECTURE.md)** | Text & ASCII Flowcharts | **Master Platform Specification:** Detailed breakdown of database relations, engine boundaries, and API request lifecycle. | **Accurate:** Matches `shared/models.py`. | **Medium:** Reference guide for technical implementation section. |
| **[docs/AGENTIC-architecture_forPaper.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/AGENTIC-architecture_forPaper.md)** | Markdown / Diagrams | **Agentic & Self-Healing Architecture:** Multi-Disciplinary Team (MDT) Clinical Guardian flow, Meta-Auditor loop, and prompt registry update workflow. | **Partially Implemented:** DB schema and prompts are present (`AuditLog`, `SystemPromptRegistry`); full subagent execution loop in `ms4_agents` is WIP. | **High:** Essential for agentic contribution section. Needs clear demarcation of implemented schema vs planned agent runtime. |
| **[ms3_user/NutriX-main/.../architecture_diagrams.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/architecture_diagrams.md)** | Mermaid Diagrams | **Recommendation & Optimization Flow:** Sequence diagram showing user goal submission $\rightarrow$ OR-Tools MILP solver $\rightarrow$ recipe output. | **Accurate:** Exactly mirrors `OptimizationEngine._solve_mip()`. | **High:** Algorithm flowchart for optimization section. |

---

## 2. Experimental Plots & Model Artifacts Inventory

Located in [runs/nutrix_custom_model-2/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/):

1. **`confusion_matrix.png` & `confusion_matrix_normalized.png`:**
   * **Description:** 123-class confusion matrix showing true vs predicted classes.
   * **WACV Use:** Figure for computer vision experimental results section.
2. **`BoxPR_curve.png` & `BoxF1_curve.png`:**
   * **Description:** Precision-Recall curve and F1-score curve across confidence thresholds $[0, 1]$.
   * **WACV Use:** Supplementary plot validating confidence threshold tuning ($0.80$ default).
3. **`results.png`:**
   * **Description:** 8-panel training loss (box, cls, dfl) and metric curves (Precision, Recall, mAP50, mAP50-95) across 30 epochs.
   * **WACV Use:** Key training convergence plot for paper appendix.
