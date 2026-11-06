# MS3 Datasets Used

Every dataset that feeds the MS3 (User & Analytics) database, which seeder loads it, and what it produces in PostgreSQL.
Counts were taken from the real files and the live database on 2026-10-30.

- **Location:** `dataset/ms3_datasets/` (git-ignored). Fast-food workbooks live in `dataset/ms3_datasets/fast_food/`.
- **Seeders:** `shared/seeders/` (run individually, or with `run_all_seeders.py`) plus `scripts/seed_yolo_classes.py`.
- **Missing files fail loudly:** each seeder calls `require_files(...)`.

## 1. Summary

| # | Dataset | Used by | Rows in file | Loaded into | Rows in DB |
|---|---|---|---|---|---|
| 1 | `Indian_Food_DF.csv` | `seed_foods.py` | 1,460 | `foods`, `food_nutrients` | 1,460 (`PACKAGED_*`) |
| 2 | `UK_fct.xlsx` | `seed_foods.py` | 144 | `foods`, `food_nutrients` | 144 (`UKFCT_*`) |
| 3 | `US_fct.xlsx` | `seed_foods.py` | 54 | `foods`, `food_nutrients` | 54 (`USFCT_*`) |
| 4 | `indian_food_nutrition_dataset.csv` | `seed_foods.py` | 97 | `foods`, `food_nutrients`, `food_portions`, `food_tags` | 98 foods, 98 portions, 196 tags (`IND_FOOD_*`) |
| 5 | `wholeFoods.xlsx` | `scripts/seed_yolo_classes.py` | 123 | `foods`, `food_nutrients` (overwrites matching names) | 14 `Whole Food` + 115 `YOLO Generic` |
| 6 | `foodAliases.xlsx` | `scripts/seed_yolo_classes.py` | 207 | `food_aliases` | 201 |
| 7 | `recipes_names.xlsx` | `seed_recipes.py` | 1,014 | `recipes` | 1,014 |
| 8 | `recipes_servingsize.xlsx` | `seed_recipes.py` | 1,014 | `servings` | 1,014 |
| 9 | `INDB.xlsx` | `seed_recipes.py` | 1,014 | `recipe_nutrition` | 1,014 |
| 10 | `recipes.xlsx` | `seed_recipes.py` | 10,271 | `recipe_ingredients` | about 12k for these recipes |
| 11 | 10 regional cuisine CSVs | `seed_recipes.py` | 217 | `recipes`, `recipe_nutrition`, `recipe_ingredients`, `servings` | 217 |
| 12 | `Indain_Food_Cuisine_Dataset.csv` | `seed_recipes.py` | 7,288 | same four tables | 7,288 (`IND_CUISINE_*`) |
| 13 | `Multi_Cuisine_Recipe_Dataset.csv` | `seed_recipes.py` | 620 | same four tables | 620 (`MULTI_CUISINE_*`) |
| 14 | 8 fast-food workbooks | `seed_fast_food.py` | 3,355 menu items | `recipes` (with `brand`), `recipe_nutrition` | 3,355 |
| 15 | `Units.xlsx` | `seed_portions.py` | 345 | `unit_conversions` | 326 |
| 16 | Built into code | `seed_rules.py` | – | `ingredient_rules`, `homely_meals` | 47 rules, 3 curated meals |

Final DB totals: `foods` 1,888 · `recipes` 12,494 · `recipe_ingredients` 109,419 · `unit_conversions` 326 · `ingredient_rules` 47 · `food_aliases` 201.
(`foods` includes 3 `LLM Inferred` rows added at runtime, not from a dataset.)

## 2. Food composition datasets

### `Indian_Food_DF.csv` (packaged foods)
- 1,460 rows, 13 columns: `name`, `brand`, `nutri_score`, `processing_score`, `nutri_energy`, `nutri_fat`, `nutri_satuFat`, `nutri_carbohydrate`, `nutri_sugar`, `nutri_fiber`, `nutri_protein`, `nutri_salt`, `food_link`.
- Becomes `foods` + `food_nutrients` with codes `PACKAGED_0000` onward. Per 100 g. Sodium = salt × 400.
- Energy cells look like `'1,994 kj\n(238 kcal)'`; the kcal figure is used (kJ ÷ 4.184 if only kJ is given).
- Used by barcode lookup and food search.

### `UK_fct.xlsx` and `US_fct.xlsx` (food composition tables)
- 144 and 54 rows, 44 columns each, plus a `notes` sheet.
- Become `foods` + `food_nutrients` (with calcium, iron, vitamin C and folate) as `UKFCT_*` and `USFCT_*`.

### `indian_food_nutrition_dataset.csv`
- 97 rows: `Food Name`, `Category`, `Serving Size`, `Calories`, `Protein`, `Carbohydrates`, `Fats`, `Dietary Preference`.
- `foods` / `food_nutrients` as `IND_FOOD_*`. The serving size (for example `1 plate (150g)`) becomes a `food_portions` row, and the diet plus "Indian" become `food_tags`.

### `wholeFoods.xlsx` and `foodAliases.xlsx` (YOLO classes)
- `wholeFoods.xlsx`: 123 canonical foods with kcal, protein, carbs, fat, fibre, sodium, sugar, saturated fat, calcium, iron, vitamin C, folate.
- `foodAliases.xlsx`: 207 rows of regional synonyms mapped to the canonical names (for example "seb" for Apple).
- Loaded by `scripts/seed_yolo_classes.py`. Macros here **overwrite** a same-named food (for example Poha, Kheer, Jalebi). MS1 uses them to resolve camera detections.

## 3. Recipe datasets

### Base library (home-style Indian recipes, 1,014 recipes)
| File | Rows | Provides |
|---|---|---|
| `recipes_names.xlsx` | 1,014 | recipe code, name, source (`asc_manual` 490, `bfp_manual` 376, `open_source_recipes` 148) |
| `recipes_servingsize.xlsx` | 1,014 | number and size of servings, unit |
| `INDB.xlsx` | 1,014 | per-100 g and per-serving nutrition (82 columns) |
| `recipes.xlsx` | 10,271 | ingredient lines with amounts and units, linked to food codes |

### Regional cuisines (10 CSVs, 217 recipes)
`bengali_foods` (22), `chinese_foods` (20), `gujarati_kathiyawadi_foods` (23), `italian_foods` (20), `japanese_foods` (20), `maharashtrian_foods` (22), `mexican_foods` (20), `punjabi_foods` (21), `rajasthani_foods` (27), `south_indian_foods` (22).
Columns: dish name, instructions, calories, key nutrients, ingredients, dietary tag. Codes `REG_<CUISINE>_nnnn`. Macros are parsed from the text columns.

### Large cuisine corpora
| File | Rows | Codes | Notes |
|---|---|---|---|
| `Indain_Food_Cuisine_Dataset.csv` (spelling as shipped) | 7,288 | `IND_CUISINE_nnnnn` | Dish, cuisine, ingredients, instructions. Flat estimate of 300 kcal / 10 g protein / 40 g carbs / 12 g fat per serving. |
| `Multi_Cuisine_Recipe_Dataset.csv` | 620 | `MULTI_CUISINE_nnnnn` | International recipes. Flat estimate of 320 kcal / 12 g / 42 g / 12 g. |

Their macros are estimates, not measured values. Diet tags (Jain, vegan and so on) come from `scripts/retag_recipes.py`, which tags recipes from their ingredients.

### Fast food (8 workbooks, 3,355 items)
`Starbucks_Beverage_Nutrition_Data` (2,266) · `Pizza_Hut_Nutrition_Dietary_Data` (303) · `KFC_Nutrition_Allergen_Data` (231) · `Subway_Nutrition_Dietary_Data` (145) · `McDonalds_Nutrition_Data-gpt` (144) · `Burger_King_India_Nutrition_Dietary` (123) · `Dominos_Nutrition_Data` (90) · `Taco_Bell_Nutrition_Dietary_Data` (53).
Stored as `recipes` with a `brand` and `dietary_tag` (the chain's published tag, which retagging leaves alone). Extra sheets (allergens, OCR text, notes) are not loaded as tables.

## 4. Portions and rules

- **`Units.xlsx`** (345 rows: food item, unit, gram weight): household measures such as katori, tbsp and piece converted to grams. 326 rows load into `unit_conversions`. The rest have no usable gram weight. Used by the Homely Builder.
- **Dietary rules and curated meals** (in `seed_rules.py`, not a file): 47 `ingredient_rules` (Jain, vegetarian, eggetarian and vegan exclusions) and 3 approved starter homely meals (Vada pav, Ghee Rice, Poha). Seed script: `seed_rules.py`.

## 5. In the folder but not used by MS3

| File | Note |
|---|---|
| `USDA_nrf.xlsx` | 270 rows. No MS3 seeder or script reads it. |
| `seed_aliases.py` | Intentionally does nothing; aliases come from `foodAliases.xlsx` through the YOLO seeder. |

The ground-truth repository (`ms3_user/NutriX-Regional-MS3-main/`) also contains USDA FoodData Central CSVs, `Indian_Food_Nutrition_Processed.csv`, `Indian_Food_Ingredients_Nutrition_CookingMethods.csv`, `foods_dataset_.csv` and `recipe_links.xlsx`. None are copied into `dataset/ms3_datasets/` or used by the MS3 seeders.

## 6. Re-seeding

```bash
cd /home/harsh/Nutrix && source .venv/bin/activate
PYTHONPATH=. python -m shared.seeders.seed_foods
PYTHONPATH=. python -m shared.seeders.seed_recipes
PYTHONPATH=. python -m shared.seeders.seed_portions
PYTHONPATH=. python -m shared.seeders.seed_rules
PYTHONPATH=. python scripts/retag_recipes.py --apply    # tag any untagged recipes
```

`seed_fast_food.py` and `scripts/seed_yolo_classes.py` are separate. The four seeders above are safe to re-run.
