# WACV 2027 Audit: Baseline Evaluation & 123-Class Results

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Verified Empirical Results, Loss Progression, Metric Trajectories, and 123-Class Accuracy Table.

---

## 1. BASELINE EVALUATION RESULTS (FINAL MODEL `nutrix_custom_model-2`)

All metrics extracted directly from [runs/nutrix_custom_model-2/results.csv](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv) (Epoch 30):

| Evaluation Metric | Final Value (Epoch 30) | Peak Measured Value | Epoch of Peak | Evidence File / Source Path |
| :--- | :--- | :--- | :--- | :--- |
| **Precision (B)** | **0.7108 (71.08%)** | 0.7167 (71.67%) | Epoch 28 | [runs/nutrix_custom_model-2/results.csv#L31](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv#L31) |
| **Recall (B)** | **0.5132 (51.32%)** | 0.5232 (52.32%) | Epoch 16 | [runs/nutrix_custom_model-2/results.csv#L17](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv#L17) |
| **mAP@50 (B)** | **0.5878 (58.78%)** | **0.5932 (59.32%)** | **Epoch 27** | [runs/nutrix_custom_model-2/results.csv#L28](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv#L28) |
| **mAP@50-95 (B)** | **0.4056 (40.56%)** | **0.4056 (40.56%)** | **Epoch 30** | [runs/nutrix_custom_model-2/results.csv#L31](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/results.csv#L31) |
| **F1 Score** | `NOT FOUND` | Visual Curve Only | N/A | [runs/nutrix_custom_model-2/BoxF1_curve.png](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/nutrix_custom_model-2/BoxF1_curve.png) |
| **Inference Speed / FPS / Latency** | `NOT FOUND` | Unrecorded in log | N/A | No inference speed benchmark output log saved in `runs/` |
| **Validation Box Loss** | **1.1489** | 1.1489 (Min) | Epoch 30 | `results.csv` Col 10 |
| **Validation Class Loss** | **0.9931** | 0.98998 (Min) | Epoch 24 | `results.csv` Col 11 |
| **Validation DFL Loss** | **1.4436** | 1.4436 (Min) | Epoch 30 | `results.csv` Col 12 |

---

## 2. COMPLETE 123-CLASS EVALUATION TABLE

Extracted directly from [runs/class_accuracies.txt](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/runs/class_accuracies.txt):

| Class ID | Class Name | Precision (P) | Recall (R) | mAP50 | Status / Note |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | almond | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 1 | aloogobi | 0.8495 | 0.7058 | 0.8539 | Verified |
| 2 | aloomasala | 0.6768 | 0.8205 | 0.8745 | Verified |
| 3 | apple | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 4 | artichoke | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 5 | ash gourd -kubhindo- | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 6 | asparagus | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 7 | avocado | 0.9370 | 0.7942 | 0.9298 | Verified |
| 8 | bamboo shoots -tama- | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 9 | banana | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 10 | beans | 0.8877 | 0.5977 | 0.7249 | Verified |
| 11 | beet | 0.7916 | 0.9497 | 0.9595 | Verified |
| 12 | bell pepper | 0.8877 | 0.8627 | 0.8885 | Verified |
| 13 | bhatura | 0.7937 | 0.8401 | 0.9044 | Verified |
| 14 | bhindimasala | 0.8286 | 0.8667 | 0.9132 | Verified |
| 15 | biryani | 0.8415 | 0.8258 | 0.9234 | Verified |
| 16 | bitter gourd | 1.0000 | 0.5453 | 0.9268 | Verified |
| 17 | black beans | 1.0000 | 0.0000 | 0.0000 | Low Recall |
| 18 | blackberry | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 19 | blueberry | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 20 | bottle gourd -lauka- | 1.0000 | 0.0000 | 0.1221 | Low Recall |
| 21 | bread | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 22 | brinjal | 1.0000 | 0.0000 | 0.0000 | Low Recall (Duplicate Class ID) |
| 23 | broad beans -bakullo- | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 24 | broccoli | 0.8366 | 0.6464 | 0.7794 | Verified |
| 25 | brussels sprouts | 0.8499 | 0.8816 | 0.9175 | Verified |
| 26 | buff meat | 1.0000 | 0.0000 | 0.0000 | Low Recall |
| 27 | cabbage | 0.8229 | 0.6919 | 0.7886 | Verified |
| 28 | capsicum | 1.0000 | 0.0000 | 0.3961 | Low Recall (Duplicate Class ID) |
| 29 | carrot | 0.7021 | 0.4587 | 0.5871 | Verified |
| 30 | cauliflower | 0.8959 | 0.9007 | 0.9555 | Verified |
| 31 | celery | 0.7224 | 0.8163 | 0.8164 | Verified |
| 32 | chai | 0.7125 | 0.6609 | 0.6943 | Verified |
| 33 | cherry | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 34 | chicken | 0.5801 | 0.3333 | 0.3469 | Low AP50 |
| 35 | chicken gizzards | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 36 | chickpeas | 1.0000 | 0.0000 | 0.0000 | Low Recall |
| 37 | chili pepper -khursani- | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 38 | chole | 0.7992 | 0.9167 | 0.9340 | Verified |
| 39 | coconutchutney | 0.6693 | 0.8522 | 0.7950 | Verified |
| 40 | corn | 0.9508 | 0.9554 | 0.9824 | Verified |
| 41 | cucumber | 0.7687 | 0.7755 | 0.8591 | Verified |
| 42 | dal | 0.9264 | 0.8387 | 0.9239 | Verified |
| 43 | dosa | 0.8118 | 0.5733 | 0.6796 | Verified |
| 44 | dumaloo | 0.7967 | 0.7126 | 0.8359 | Verified |
| 45 | egg | 0.6078 | 0.0636 | 0.2334 | Low AP50 |
| 46 | eggplant | 0.9207 | 0.7141 | 0.8714 | Verified |
| 47 | farsi ko munta | 1.0000 | 0.0000 | 0.2475 | Low Recall |
| 48 | fiddlehead ferns -niguro- | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 49 | fish | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 50 | fishcurry | 0.6962 | 0.5589 | 0.6307 | Verified |
| 51 | garlic | 0.8707 | 0.8593 | 0.9030 | Verified |
| 52 | ghevar | 0.7178 | 0.5208 | 0.6886 | Verified |
| 53 | grape | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 54 | green bean | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 55 | green brinjal | 0.0786 | 0.5000 | 0.4950 | Verified |
| 56 | green gram | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 57 | green lentils | 1.0000 | 0.0000 | 0.0000 | Low Recall |
| 58 | green onion | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 59 | green peas | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 60 | green soyabean -hariyo bhatmas- | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 61 | greenchutney | 0.8060 | 0.7556 | 0.8227 | Verified |
| 62 | gulabjamun | 0.9024 | 0.7628 | 0.9104 | Verified |
| 63 | gundruk | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 64 | hot pepper | 0.8285 | 0.7714 | 0.8497 | Verified |
| 65 | idli | 0.7523 | 0.9425 | 0.9132 | Verified |
| 66 | jack fruit | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 67 | jalebi | 0.9551 | 0.9744 | 0.9914 | **Top Performing** |
| 68 | kebab | 0.7387 | 0.5618 | 0.7022 | Verified |
| 69 | kheer | 0.7568 | 0.7800 | 0.8156 | Verified |
| 70 | kiwi | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 71 | kulfi | 0.9127 | 0.7575 | 0.8527 | Verified |
| 72 | lassi | 0.7817 | 0.7321 | 0.8623 | Verified |
| 73 | lemon | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 74 | lettuce | 0.8101 | 1.0000 | 0.9801 | Verified |
| 75 | lime | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 76 | long beans -bodi- | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 77 | mandarin | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 78 | masyaura | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 79 | minced meat | 1.0000 | 0.0000 | 0.4783 | Low Recall |
| 80 | mushroom | 0.0000 | 0.0000 | 0.0001 | Low AP50 |
| 81 | mutton | 1.0000 | 0.0000 | 0.0650 | Low Recall |
| 82 | muttoncurry | 0.6308 | 0.7500 | 0.7465 | Verified |
| 83 | onion | 0.9009 | 0.8927 | 0.9376 | Verified |
| 84 | onionpakoda | 0.9074 | 0.9801 | 0.9907 | **Top Performing** |
| 85 | orange | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 86 | palakpaneer | 0.9495 | 0.9778 | 0.9636 | Verified |
| 87 | papaya | 1.0000 | 0.0000 | 0.1753 | Low Recall |
| 88 | pattypan squash | 0.9075 | 0.9339 | 0.9715 | Verified |
| 89 | pea | 0.4604 | 0.5238 | 0.4245 | Low AP50 |
| 90 | peach | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 91 | pear | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 92 | pineapple | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 93 | poha | 0.9367 | 0.9143 | 0.9663 | Verified |
| 94 | potato | 0.6631 | 0.7992 | 0.7857 | Verified |
| 95 | pumpkin | 0.8493 | 0.8710 | 0.9166 | Verified |
| 96 | pumpkin -farsi- | 0.7913 | 0.2308 | 0.2684 | Low AP50 |
| 97 | radish | 0.9047 | 0.8465 | 0.9114 | Verified |
| 98 | rahar ko daal | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 99 | rajmacurry | 0.9467 | 0.8810 | 0.9138 | Verified |
| 100 | rasmalai | 0.8802 | 0.8750 | 0.9117 | Verified |
| 101 | raspberry | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 102 | red beans | 1.0000 | 0.0000 | 0.0340 | Low Recall |
| 103 | red lentils | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 104 | rice -chamal- | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 105 | samosa | 0.7497 | 0.6491 | 0.7298 | Verified |
| 106 | shahipaneer | 0.8309 | 0.4917 | 0.6941 | Verified |
| 107 | soyabean-bhatmas- | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 108 | sponge gourd -ghiraula- | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 109 | squash -iskus- | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 110 | stinging nettle -sisnu- | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 111 | strawberry | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 112 | sweet potato -suthuni- | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 113 | tomato | 0.7589 | 0.7398 | 0.8091 | Verified |
| 114 | tree tomato -rukh tamatar- | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 115 | turnip | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 116 | vegetable marrow | 0.7231 | 0.9525 | 0.9270 | Verified |
| 117 | wallnut | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 118 | watermelon | 0.0000 | 0.0000 | 0.0000 | No Val Images |
| 119 | wheat | 0.0000 | 0.0000 | 0.0000 | Low Recall |
| 120 | whiterice | 0.8551 | 0.7627 | 0.8482 | Verified |
| 121 | yam -pidalu- | 1.0000 | 0.0000 | 0.9950 | High AP50 / Low R |
| 122 | yellow lentils | 1.0000 | 0.0000 | 0.0000 | Low Recall |

---

## 3. CLASS PERFORMANCE SUMMARY

* **Top 5 Best-Performing Classes (AP50 > 0.96):**
  1. `jalebi`: AP50 = **0.9914**, Precision = 0.9551, Recall = 0.9744
  2. `onionpakoda`: AP50 = **0.9907**, Precision = 0.9074, Recall = 0.9801
  3. `corn`: AP50 = **0.9824**, Precision = 0.9508, Recall = 0.9554
  4. `lettuce`: AP50 = **0.9801**, Precision = 0.8101, Recall = 1.0000
  5. `pattypan squash`: AP50 = **0.9715**, Precision = 0.9075, Recall = 0.9339
* **Worst-Performing Evaluated Classes (AP50 < 0.40):**
  1. `egg`: AP50 = **0.2334**, Precision = 0.6078, Recall = 0.0636
  2. `pumpkin -farsi-`: AP50 = **0.2684**, Precision = 0.7913, Recall = 0.2308
  3. `chicken`: AP50 = **0.3469**, Precision = 0.5801, Recall = 0.3333
