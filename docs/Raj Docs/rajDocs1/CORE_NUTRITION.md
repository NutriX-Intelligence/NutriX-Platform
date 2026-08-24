# WACV 2027 Technical Audit: Core Nutrition Knowledge Module

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Nutrition Databases, Clinical Formulas, Gram Conversion, Fuzzy Ingredient Normalization, and Health Scoring.

---

## 1. Overview of Nutrition Data Sources

This repository integrates multiple authoritative regional and international nutrition datasets to support precise dietary calculations:

1. **ICMR / NIN / IFCT (Indian Food Composition Tables):**
   * **Source File:** [dataset/ms3_datasets/INDB.xlsx](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/ms3_datasets/INDB.xlsx) (1.06 MB)
   * **Database Mapping:** Populates `foods` and `food_nutrients` tables. Provides per-100g values for Indian raw ingredients (dal, paneer, ghee, spices, local grains).
2. **USDA National Nutrient Database (FoodData Central):**
   * **Source File:** [dataset/ms3_datasets/USDA_nrf.xlsx](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/ms3_datasets/USDA_nrf.xlsx) (41.8 KB)
   * **Database Mapping:** Populates `foods` and `food_nutrients` tables for global produce and standard commodities.
3. **Open Food Facts (OFF API):**
   * **Integration:** Tier 1 web lookup in [ms3_user/NutriX-main/NutriX-main/app/services/barcode_service.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/barcode_service.py) for packaged food products.
4. **Master Recipe Database:**
   * **Source File:** [dataset/ms3_datasets/recipes.xlsx](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/dataset/ms3_datasets/recipes.xlsx) (714 KB)
   * **Database Mapping:** Populates `recipes`, `recipe_ingredients`, `recipe_nutrition`, and `servings` tables.

---

## 2. Mathematical & Clinical Nutrition Formulations

All energy and macronutrient target calculations are implemented in [ms3_user/NutriX-main/NutriX-main/app/services/nutrition_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/nutrition_engine.py):

### 2.1 Body Mass Index (BMI)
$$\text{BMI} = \frac{\text{weight (kg)}}{(\text{height (m)})^2}$$

### 2.2 Basal Metabolic Rate (BMR — Mifflin-St Jeor Equation)
$$\text{BMR} = 10 \times \text{weight (kg)} + 6.25 \times \text{height (cm)} - 5 \times \text{age (years)} + s$$
where $s = +5$ for males, and $s = -161$ for females.

### 2.3 Total Daily Energy Expenditure (TDEE)
$$\text{TDEE} = \text{BMR} \times \text{ActivityMultiplier}$$
Multipliers:
* Sedentary: $1.2$
* Lightly Active: $1.375$
* Moderately Active: $1.55$
* Active: $1.725$
* Very Active: $1.9$

### 2.4 Goal-Based Caloric Target Adjustments
* **Fat Loss:** $\text{TargetCal} = \text{TDEE} - 500 \text{ kcal}$ (Safety Floor: 1500 kcal for male, 1200 kcal for female)
* **Weight Gain:** $\text{TargetCal} = \text{TDEE} + 500 \text{ kcal}$
* **Muscle Gain:** $\text{TargetCal} = \text{TDEE} + 300 \text{ kcal}$
* **Maintenance:** $\text{TargetCal} = \text{TDEE}$

### 2.5 Macronutrient Gram Calculations
* **Protein (4 kcal/g):** $\text{Protein (g)} = \frac{\text{TargetCal} \times P_{\text{pct}}}{4.0}$
* **Carbohydrates (4 kcal/g):** $\text{Carbs (g)} = \frac{\text{TargetCal} \times C_{\text{pct}}}{4.0}$
* **Fat (9 kcal/g):** $\text{Fat (g)} = \frac{\text{TargetCal} \times F_{\text{pct}}}{9.0}$

Goal-specific macro ratio splits ($P_{\text{pct}}, C_{\text{pct}}, F_{\text{pct}}$):
* Fat Loss: 30% Protein / 40% Carbs / 30% Fat
* Weight Gain: 25% Protein / 50% Carbs / 25% Fat
* Muscle Gain: 30% Protein / 45% Carbs / 25% Fat
* Maintenance: 25% Protein / 45% Carbs / 30% Fat

---

## 3. Serving-Size Normalization & Gram Conversion Engine

Implemented in [ms3_user/NutriX-main/NutriX-main/app/services/homely_meals_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/homely_meals_engine.py) (`parse_gram_weight`):

1. **Database Direct Lookup:** Queries `unit_conversions` table for exact match on `(food_item, unit)`.
2. **Database Overlap Matching:** Matches partial terms against `unit_conversions` table if exact match is absent.
3. **Standard Household Unit Fallback Rules:**
   * `tsp` / `teaspoon` $\rightarrow 5.0\text{ g}$
   * `tbsp` / `tablespoon` $\rightarrow 15.0\text{ g}$
   * `cup` / `c` $\rightarrow 240.0\text{ g}$
   * `glass` $\rightarrow 200.0\text{ g}$
   * `bowl` $\rightarrow 200.0\text{ g}$
   * `piece` / `pcs` / `slice` $\rightarrow 50.0\text{ g}$
   * `pinch` / `dash` $\rightarrow 1.0\text{ g}$
   * `g` / `gram` / `ml` $\rightarrow 1.0\text{ g}$

---

## 4. RapidFuzz & Culinary Synonym Matching Engine

Implemented in [ms3_user/NutriX-main/NutriX-main/app/services/ingredient_matcher.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/ingredient_matcher.py):

* **RapidFuzz Library:** Uses `token_sort_ratio` and `partial_ratio` with score threshold $\text{MIN\_FUZZY\_SCORE} = 78$.
* **Curated Indian/Global Synonym Dictionary (`SYNONYM_MAP`):** Over 80+ mappings handling regional variants:
  * `capsicum` $\rightarrow$ `bell pepper`
  * `dahi` / `curd` $\rightarrow$ `yogurt`
  * `aloo` $\rightarrow$ `potato`
  * `pyaaz` $\rightarrow$ `onion`
  * `dhaniya` $\rightarrow$ `cilantro`
  * `baingan` / `aubergine` $\rightarrow$ `eggplant`
  * `bhindi` / `ladyfinger` $\rightarrow$ `okra`
  * `besan` $\rightarrow$ `gram flour`
  * `sooji` / `rava` $\rightarrow$ `semolina`
  * `palak` / `saag` $\rightarrow$ `spinach`
  * `ghee` $\rightarrow$ `ghee`
  * `toor dal` / `chana dal` / `moong dal` / `masoor dal` $\rightarrow$ `dal`
* **Composite Recipe Matching Score Formula:**
  $$\text{MatchScore} = 0.7 \times \text{QueryCoverage} + 0.3 \times \text{RecipeCoverage}$$
  where:
  $$\text{QueryCoverage} = \frac{|\text{Matched User Ingredients}|}{|\text{Total User Ingredients}|}$$
  $$\text{RecipeCoverage} = \frac{|\text{Matched Recipe Ingredients}|}{|\text{Total Recipe Ingredients}|}$$
