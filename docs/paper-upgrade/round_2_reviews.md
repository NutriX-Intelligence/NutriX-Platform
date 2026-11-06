# Round 2 Reviews — Submission 3455

---

## Meta Review of Submission 3455 by Area Chair muk5

**Meta Review by Area Chair muk5**  
*Date:* 06 Oct 2026, 10:05 (modified: 15 Oct 2026, 09:35)  
*Visibility:* Senior Area Chairs, Area Chairs, Program Chairs, Authors, Reviewers  
*Status:* Submitted  

### Metareview:
There is a clear consensus to reject (1/2/3) from high- and expert-confidence reviewers, and all three reviews are detailed and high quality reviews. They agree the decoupled vision/knowledge design is sensible, but key components are unvalidated: there is no end-to-end evaluation from image to meal plan, the barcode/OCR pathways are untested, the knowledge layer and normalization are unmeasured, and the core normalization method is not even described. The detection numbers are hard to interpret given the imbalanced validation data. The meal-planning results are weak. The final decision is reject.

**Final Recommendation:** Reject in round 2

---

## Official Review by Reviewer Qmr2

**Title:** Great framework with several things to improve  
**Date:** 25 Sept 2026, 22:39 (modified: 15 Oct 2026, 09:19)  
**Visibility:** Program Chairs, Senior Area Chairs, Area Chairs, Reviewers, Reviewer Qmr2, Authors  
**Status:** Submitted  
**Paper Track:** Application  

### Paper Summary:
The paper presents Nutrix, a framework that separates visual food recognition from a broader food-knowledge layer (217 regional classes across 10 cuisines), linking both to structured nutritional information (IFCT, USDA) and to a constrained meal-planning module solved with OR-Tools/SCIP. The detector achieves 58.78% mAP@50 on the 123-class test set and 81.56% mAP@50 on a 31-class Indian-food subset. The paper also presents experiments on semantic label normalization, rotational robustness, qualitative error analysis, and a meal-planning benchmark over 80 instances.

### Paper Strengths:
1. The idea of decoupling the visual taxonomy (123 classes) from the nutrition-knowledge taxonomy (217 classes) is well motivated and explicitly addressed.
2. The semantic normalization experiment (brinjal/eggplant, capsicum/bell pepper) is an interesting contribution: it concretely shows how taxonomy fragmentation can inflate measured error, and the numbers (e.g., 0% recall for "brinjal" vs. 71.41% for "eggplant") are a good illustrative example.
3. The authors are transparent about the system's limitations (Section 6), including the fact that the 217-class regional layer is not validated as a visual benchmark.
4. The end-to-end system is described with clear architectural detail, and represents a non-trivial attempt to connect perception and decision-making in a real applied domain.

### Major Weaknesses:
1. **Extremely imbalanced validation/test coverage.** The median number of validation images per class is 3, with 37 out of 123 classes entirely absent from the validation set and only 51 classes having more than 20 images (Table 4, Fig. 2a). This makes the aggregate metrics (58.78% mAP@50) difficult to interpret as a uniform performance estimate, and severely undermines the reliability of the comparison with the "Indian food" subset (81.56% mAP@50)—the paper itself acknowledges that the gap does not reflect an inherently easier recognition task for these classes, but does not quantify how much of the gap is simply due to a smaller, more favorably represented subset of classes selected post-hoc.
2. **Multimodal pathways (barcode/OCR) not evaluated.** Barcode scanning and OCR are presented as key components of the system (Section 3.3, contributions in the Introduction), but no quantitative results are reported (barcode-reading accuracy, OCR precision, fallback rate). Without these numbers it is impossible to judge whether the "multimodal" system provides a real advantage or is only architecturally planned.
3. **Regional knowledge layer not validated.** The 217 classes / 10 cuisines are described only qualitatively; there is no measure of coverage, correctness, or quality of the nutrition grounding (e.g., accuracy of name-to-canonical-identity normalization, error in retrieved nutritional values). This is one of the two stated pillars of the framework, yet it remains essentially untested.
4. **Meal-planning benchmark with weak and under-discussed results.** Feasibility ranges only from 40% to 50% (Table 8), with calorie error of ~21–23% and protein error of ~28%, fairly high values for a system intended for practical nutritional use. Moreover, feasibility decreases when moving from a pool of 50 to larger pools (50% $\rightarrow$ 40%), a counterintuitive result (a larger pool should offer more options, not fewer) that is not discussed. The sample is also small (20 instances per pool size).
5. **Lack of direct quantitative comparisons.** Table 1 compares Nutrix with related work only via qualitative checkmarks without any direct numerical comparison on a shared benchmark with any of the cited systems (Food-101, Nutrition5k, NutrifyAI, etc.).
6. **No measure of variability/uncertainty.** All results (detection, rotation, meal planning) are reported as single point estimates, without confidence intervals, standard deviations, or statistical tests, even where the sample is small (e.g., 31 Indian classes, 200 images for rotational robustness, 20 instances per pool in meal planning).

### Minor Weaknesses:
- The train/val/test split criterion is not specified (random? stratified by class? by source dataset?), which is relevant information given the strong imbalance reported in Table 4.
- Table 8 would benefit from also reporting the number of recipes actually available per candidate pool relative to the 9,139 total recipes, to better understand why larger pools do not improve feasibility.

### Round 2 Recommendation:
**3: Borderline Reject**

### Round 2 Justification:
The framework is well conceived from a systems perspective and the transparency about its limitations is appreciated, but several key components (multimodality, regional knowledge layer, meal planning) lack sufficient quantitative validation, and the reported detection metrics are difficult to interpret due to the strong imbalance in the validation/test dataset. For this reason I think that this work is not ready for publication in this venue.

**Confidence Level:** 5 - Expert: The reviewer is an authority in the specific subfield addressed by the paper. They are extremely confident in their evaluation and understanding of the work.

---

## Official Review by Reviewer GHiW

**Title:** Interesting work but lack validation  
**Date:** 25 Sept 2026, 18:26 (modified: 15 Oct 2026, 09:19)  
**Visibility:** Program Chairs, Senior Area Chairs, Area Chairs, Reviewers, Reviewer GHiW, Authors  
**Status:** Submitted  
**Paper Track:** Application  

### Paper Summary:
This paper presents Nutrix, a framework connecting food detection with nutrition knowledge and constrained meal planning. It combines a YOLOv8n detector covering 123 food categories, complementary barcode and OCR pathways, a regional knowledge layer containing 217 food concepts across 10 cuisines, and an OR-Tools/SCIP meal planner. Experiments examine detection performance, semantic label normalization, rotational robustness, and recipe-planning feasibility.

### Paper Strengths:
1. The paper addresses a practically relevant problem with potential applications in dietary tracking, personalized nutrition, and meal recommendation. Incorporating culturally diverse food knowledge broadens the intended scope of the system.
2. Connecting visual recognition, canonical food identities, and explicit dietary constraints is an interesting application-oriented integration. Separating visual categories from the broader knowledge layer is a useful design choice for accommodating heterogeneous food names and regional information.

### Major Weaknesses:
1. **The central application lacks end-to-end evaluation.** Section 4.4 evaluates meal planning independently of food detection, so the experiments do not establish whether recognized foods are correctly mapped to nutritional information or improve the resulting plans. Barcode and OCR pathways are also unevaluated, and no ablations establish the contribution of the regional knowledge layer or canonical representation.
2. **The methodological exploration and comparative evaluation are limited.** The system relies on an existing detector, knowledge lookup, and a standard constraint solver, but provides little analysis of why these choices are appropriate. In particular, why is YOLOv8n selected? No comparison with alternative detectors or a pretrained vision-language model using the same downstream resources is provided. Comparisons on matched tasks, including accuracy, inference cost, and downstream performance, would help justify this choice. Table 1 only compares advertised capabilities and cannot establish an advantage of the proposed integration.
3. **The evaluation does not adequately support the claimed breadth of coverage.** Section 5 reports 37 classes with no validation images and another 30 with fewer than five, with a median of three images per class. The cultural evaluation is limited to an Indian-food validation subset, while the accuracy and usefulness of the broader 217-concept knowledge layer are not quantitatively assessed. Semantic normalization is examined for only two synonym groups, which provides limited evidence for the general mapping mechanism.
4. **The downstream results are not sufficiently convincing.** Without a matched planning baseline, a clear instance-generation protocol, and analysis of the failure causes, these results do not establish practical effectiveness. The optimization objective or feasibility formulation and treatment of infeasible cases in error reporting also need clearer specification.

### Minor Weaknesses:
- Figure 3 is difficult to read because the font is too small.
- The abstract describes the detector as "trained" on 56,147 images, but Table 2 actually lists only 51,535 in the training split.

### Round 2 Recommendation:
**2: Weak Reject**

### Round 2 Justification:
Although the paper explores an interesting system design with broad application potential, the experiments do not establish a convincing benefit from the proposed integration. The absence of end-to-end validation, limited exploration of alternative methods, inadequate evaluation coverage, and weak planning results leave the central application claims insufficiently supported. These concerns require substantial additional experiments and methodological detail.

**Confidence Level:** 5 - Expert: The reviewer is an authority in the specific subfield addressed by the paper. They are extremely confident in their evaluation and understanding of the work.

---

## Official Review by Reviewer ybHw

**Title:** Lack of concrete description of the canonical normalization and end-to-end application evaluation.  
**Date:** 24 Sept 2026, 21:17 (modified: 15 Oct 2026, 09:19)  
**Visibility:** Program Chairs, Senior Area Chairs, Area Chairs, Reviewers, Reviewer ybHw, Authors  
**Status:** Submitted  
**Paper Track:** Application  

### Paper Summary:
Building a system that automatically estimates nutrition from meal images requires linking visual food recognition with food knowledge resources such as recipes, ingredients, and nutrition data. However, the class labels of the visual taxonomy do not necessarily match the granularity of the food knowledge categories, which are organized by ingredients, recipes, nutritional attributes, and regional names. This paper proposes a framework that keeps visual recognition separate from food knowledge and connects the two through food identity normalization. The vision component uses YOLOv8n trained on 56,147 images across 123 food classes, achieving 58.78% mAP@50 and 40.56% mAP@50:95 on the 123-class test set. Complementary identification via barcodes and OCR is integrated, together with a regional food knowledge layer of 217 classes across 10 cuisines, which grounds recognized foods in nutrition and recipe information. Meal planning is formulated as constrained optimization with Google OR-Tools that assigns recipes to four meal slots.

### Paper Strengths:
1. The paper correctly identifies that the class granularity of visual food recognition does not align with that of food knowledge resources (recipes, ingredients, nutrition data), which are built in different contexts. Rather than merging the two, it keeps them separate and connects them via a canonical food-identity mapping, which is a reasonable design choice.
2. The system also covers packaged foods via barcode and OCR pathways, not just home-cooked dishes, showing that it targets a practical, real-world task.

### Major Weaknesses:
1. The central contribution of this paper is connecting visual and food knowledge categories of different granularities via canonical food-identity normalization, yet the concrete implementation of this normalization is not described. Since such taxonomy mismatches are not specific to meal image nutrition estimation, this is a potentially important contribution that deserves a concrete, reproducible method.
2. The 123 visual classes and 217 regional food knowledge classes seem too few for a real-world meal image nutrition assessment scenario. The paper itself does not treat the 217-class layer as a complete visual benchmark. On the other hand, if this number of categories is genuinely sufficient, then the correspondence between visual and food knowledge categories (i.e., the normalization step) could plausibly be built by hand, which would weaken the paper's central motivation.
3. Module-level evaluations (e.g., visual category detection) are provided, but there is no end-to-end evaluation of the system in a practical setting. As an Applications Track submission, this necessarily limits the strength of the evaluation.
4. The paper's claims are hard to follow overall. The authors should first explain with concrete examples what application is proposed and what the user experience would be like.

### Minor Weaknesses:
- Please show with a concrete example how a meal image is processed by the proposed method and what the final output is. As it stands, the results report only module-level metrics and the qualitative examples in Fig. 3 cover detection errors only, without any end-to-end example such as:  
  $$\text{meal image} \longrightarrow \text{detected foods} \longrightarrow \text{canonical identities} \longrightarrow \text{nutrition values} \longrightarrow \text{meal plan}$$
- Meal management applications with image-based input are already widely available, including commercial ones. The related work compares only academic systems and datasets, and the capability comparison in Table 1 is explicitly qualitative. The authors should more thoroughly survey such existing applications and clearly state what advantages the proposed method offers over them.

### Round 2 Recommendation:
**1: Reject**

### Round 2 Justification:
The design philosophy of separating visual recognition from food knowledge and connecting the two through normalization is reasonable. However, the concrete implementation of the food-identity normalization, which is the core of this contribution, is not described, and given the scale of the categories (123 visual classes / 217 knowledge classes), a handcrafted mapping would suffice so the paper does not convincingly solve a practical problem. Module-level evaluations are provided, but there is no end-to-end evaluation from meal images to the final meal-plan output, which is insufficient as practical evidence for an Applications Track submission.

**Confidence Level:** 4 - High Confidence: The reviewer has strong expertise in the area. They are highly familiar with the relevant literature and can critically evaluate the paper.