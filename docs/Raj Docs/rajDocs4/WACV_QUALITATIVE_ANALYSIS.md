# WACV 2027 Qualitative Error Analysis Report

**Evaluated Checkpoint:** `runs/nutrix_custom_model-2/weights/best.pt`  
**Validation Dataset Path:** `dataset/custom_training_data/valid/images`  

## Qualitative Error Category Breakdown

| Category ID | Image Filename | Saved Visual Image | Ground Truth | Prediction | Confidence | Error Category |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `palak-paneer-recipe-5-_jpg.rf.b15d2eb0d0bdd215bf0646f01bf2aa2e.jpg` | `docs/rajDocs4/wacv_figures/qualitative/1_high_conf_correct.jpg` | palakpaneer | palakpaneer, coconutchutney, dosa | 0.8792 | High-Confidence Correct Detection |
| 2 | `images-23-_jpg.rf.119409f30e02fc363828dc6099e86270.jpg` | `docs/rajDocs4/wacv_figures/qualitative/2_false_positive.jpg` | None (Background) | potato, garlic | 0.6367 | False Positive Detection |
| 3 | `images_jpg.rf.9c793985e464ad8a7ca5a62f358d0432.jpg` | `docs/rajDocs4/wacv_figures/qualitative/3_missed_detection.jpg` | farsi ko munta, farsi ko munta | No Detection | N/A | Missed Detection (False Negative) |
| 4 | `-10_jpg.rf.557762ad8ef05ae3d44e9ff2469bedaf.jpg` | `docs/rajDocs4/wacv_figures/qualitative/4_visually_similar_confusion.jpg` | beans | pea, pea, pea, pea, pea, pea, pea, pea, pea, pea, pea, pea, pea, pea | 0.7478 | Visually Similar Food Confusion |
| 5 | `img67_jpg.rf.fcd8c8004f87aea93605c97972cbbd2c.jpg` | `docs/rajDocs4/wacv_figures/qualitative/5_duplicate_semantic_confusion.jpg` | capsicum | bell pepper, tomato | 0.3567 | Duplicate Semantic Label Confusion |
| 6 | `-71_jpg.rf.4dfd1c56d135d5ad454170d7065b4e8c.jpg` | `docs/rajDocs4/wacv_figures/qualitative/6_crowded_plate.jpg` | bell pepper, bell pepper, bell pepper | bell pepper, bell pepper, bell pepper, bell pepper | 0.8485 | Crowded Plate Multi-Object Detection |
| 7 | `images-21-_jpg.rf.3b38d0318c3c2796567020034cf3a6d1.jpg` | `docs/rajDocs4/wacv_figures/qualitative/7_low_confidence.jpg` | beans | beans | 0.1749 | Low-Confidence Detection |
