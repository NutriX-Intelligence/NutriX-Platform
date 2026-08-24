Edited CORE_123_CLASSES.txt
Edited CORE_REGIONAL_MAPPING.csv
Edited CORE_REGIONAL_EXPERIMENT_PLAN.md
Edited CORE_REGIONAL_COMPATIBILITY_AUDIT.md
Listed directory rajDocs2
Edited walkthrough.md

# NutriX Core-to-Regional Compatibility Audit Completed

The technical compatibility audit between the **NutriX Core Platform** (123-class YOLOv8 computer vision model and 56,147-image dataset) and the separate **NutriX Regional Project** (217-class regional food taxonomy across 10 cuisines) has been completed.

All 4 generated audit documents are saved in [docs/rajDocs2/](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs2/):

1. **[CORE_123_CLASSES.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs2/CORE_123_CLASSES.txt)** — Formatted plain-text list of all 123 Core visual food classes extracted from `data.yaml` and `class_accuracies.txt`.
2. **[CORE_REGIONAL_MAPPING.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs2/CORE_REGIONAL_MAPPING.csv)** — Structured mapping table mapping each Core class to potential regional equivalents across the 10 target cuisines (**Punjabi, South Indian, Maharashtrian/Gujarati, Rajasthani, Bengali, Chinese, Mexican, Italian, Japanese, Global/Raw**).
3. **[CORE_REGIONAL_EXPERIMENT_PLAN.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs2/CORE_REGIONAL_EXPERIMENT_PLAN.md)** — Prioritized experimental roadmap (P0 necessary, P1 recommended, P2 optional) relying strictly on existing Core images.
4. **[CORE_REGIONAL_COMPATIBILITY_AUDIT.md](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/docs/rajDocs2/CORE_REGIONAL_COMPATIBILITY_AUDIT.md)** — Master technical audit report addressing Tasks 1–8 in full detail.

---

### Key Compatibility Findings & Answers to Research Questions

1. **Can the 217 Regional taxonomy currently be claimed as a CV benchmark?**  
   **NO.** The Regional project currently has **NO image dataset and NO trained CV model**. Claiming a 217-class CV benchmark without images or model evaluations would be scientifically invalid.
2. **Can it currently be claimed as a nutrition/food knowledge taxonomy?**  
   **YES.** The 217-class regional taxonomy with 10 cuisines, recipe formulations, and nutrient breakdowns represents a structured regional nutrition knowledge ontology.
3. **How many of the Core 123 visual classes overlap with the Regional taxonomy?**  
   **55 classes total** (22 direct prepared regional dishes like `dosa`, `idli`, `biryani`, `chole`, `palakpaneer`, `ghevar`, `poha`, + 8 regional condiments/drinks + 25 shared staple ingredients).
4. **What is the strongest scientifically defensible combined NutriX story?**  
   Position NutriX as a **Dual-Layer Architecture**:
   * **Layer 1 (Visual Perception Layer):** 123-class YOLOv8 object detector fine-tuned on 56,147 images with Human-in-the-Loop active learning adaptation.
   * **Layer 2 (Knowledge & Optimization Layer):** 217-class Regional nutrition ontology combined with Google OR-Tools Mixed-Integer Linear Programming for daily meal optimization under strict caloric/macro constraints.
5. **What experiment should be performed next?**  
   Execute the **Semantic Class Consolidation Ablation (P0-3)**: Merge duplicate visual classes (`brinjal`/`eggplant` and `capsicum`/`bell pepper`) in `data.yaml` and re-evaluate validation mAP@50.
6. **What claims must NOT appear in the WACV paper?**  
   * Do NOT claim that a 217-class computer vision detector has been trained or evaluated.
   * Do NOT claim visual detection coverage for all 10 regional cuisines (images only exist for 5 cuisines: Punjabi, South Indian, Maharashtrian/Gujarati, Rajasthani, Bengali).
   * Do NOT claim images exist in the Regional project repository.