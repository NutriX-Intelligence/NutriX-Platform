"""initial_schema_all_tables

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-08 10:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=True),
        sa.Column('google_id', sa.String(), nullable=True),
        sa.Column('avatar_url', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('google_id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. Profiles
    op.create_table(
        'profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('gender', sa.String(), nullable=True),
        sa.Column('height', sa.Float(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('activity_level', sa.String(), nullable=True),
        sa.Column('goal', sa.String(), nullable=True),
        sa.Column('diet_type', sa.String(), nullable=True),
        sa.Column('target_calories', sa.Float(), nullable=True),
        sa.Column('target_protein', sa.Float(), nullable=True),
        sa.Column('target_carbs', sa.Float(), nullable=True),
        sa.Column('target_fat', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # 3. User Preferences
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('preference_type', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 4. Goals
    op.create_table(
        'goals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('goal_type', sa.String(), nullable=True),
        sa.Column('target_weight', sa.Float(), nullable=True),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 5. Food Categories
    op.create_table(
        'food_categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # 6. Foods
    op.create_table(
        'foods',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('food_code', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('brand', sa.String(), nullable=True),
        sa.Column('barcode', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('food_code')
    )
    op.create_index('ix_foods_food_code', 'foods', ['food_code'], unique=True)

    # 7. Food Nutrients
    op.create_table(
        'food_nutrients',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('food_id', sa.Integer(), nullable=False),
        sa.Column('energy_kcal', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('protein_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('carb_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('fat_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('fibre_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('sodium_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('sugar_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('saturated_fat_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('calcium_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('iron_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('vitc_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('folate_ug', sa.Float(), server_default='0.0', nullable=True),
        sa.ForeignKeyConstraint(['food_id'], ['foods.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('food_id')
    )


    # 11. Recipes
    op.create_table(
        'recipes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recipe_code', sa.String(), nullable=False),
        sa.Column('recipe_name', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('cuisine', sa.String(), nullable=True),
        sa.Column('difficulty', sa.String(), nullable=True),
        sa.Column('cooking_time_minutes', sa.Integer(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('primarysource', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recipe_code')
    )
    op.create_index('ix_recipes_recipe_code', 'recipes', ['recipe_code'], unique=True)

    # 12. Servings
    op.create_table(
        'servings',
        sa.Column('recipe_code', sa.String(), nullable=False),
        sa.Column('no_of_servings', sa.Float(), nullable=True),
        sa.Column('size_of_servings', sa.Float(), nullable=True),
        sa.Column('servings_unit', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['recipe_code'], ['recipes.recipe_code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('recipe_code')
    )

    # 13. Recipe Ingredients
    op.create_table(
        'recipe_ingredients',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=True),
        sa.Column('recipe_code', sa.String(), nullable=True),
        sa.Column('ingredient_name', sa.String(), nullable=True),
        sa.Column('food_code', sa.String(), nullable=True),
        sa.Column('food_name', sa.String(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(), nullable=True),
        sa.Column('amount_org', sa.String(), nullable=True),
        sa.Column('unit_org', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipe_code'], ['recipes.recipe_code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 14. Recipe Nutrition
    op.create_table(
        'recipe_nutrition',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=True),
        sa.Column('recipe_code', sa.String(), nullable=True),
        sa.Column('energy_kcal', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('carb_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('protein_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('fat_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('freesugar_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('fibre_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('sodium_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('calcium_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('iron_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('vitc_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('folate_ug', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_energy_kcal', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_carb_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_protein_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_fat_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_freesugar_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_fibre_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_sodium_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_calcium_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_iron_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_vitc_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('unit_serving_folate_ug', sa.Float(), server_default='0.0', nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipe_code'], ['recipes.recipe_code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recipe_id'),
        sa.UniqueConstraint('recipe_code')
    )

    # 15. Recipe Steps
    op.create_table(
        'recipe_steps',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('instruction', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


    # 17. Ingredient Rules
    op.create_table(
        'ingredient_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ingredient_name', sa.String(), nullable=False),
        sa.Column('rule_type', sa.String(), nullable=False),
        sa.Column('value', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ingredient_rules_ingredient_name', 'ingredient_rules', ['ingredient_name'], unique=False)

    # 18. Meal Logs
    op.create_table(
        'meal_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('log_date', sa.Date(), nullable=False),
        sa.Column('meal_type', sa.String(), nullable=False),
        sa.Column('food_name', sa.String(), nullable=False),
        sa.Column('calories', sa.Float(), nullable=False),
        sa.Column('protein', sa.Float(), nullable=False),
        sa.Column('carbs', sa.Float(), nullable=False),
        sa.Column('fat', sa.Float(), nullable=False),
        sa.Column('weight_g', sa.Float(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_meal_logs_user_date', 'meal_logs', ['user_id', 'log_date'], unique=False)

    # 19. Water Logs
    op.create_table(
        'water_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount_ml', sa.Float(), nullable=False),
        sa.Column('logged_at', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 20. Weight Logs
    op.create_table(
        'weight_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('logged_at', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 21. Barcode Cache
    op.create_table(
        'barcode_cache',
        sa.Column('barcode', sa.String(), nullable=False),
        sa.Column('product_name', sa.String(), nullable=True),
        sa.Column('brand', sa.String(), nullable=True),
        sa.Column('ingredients_text', sa.String(), nullable=True),
        sa.Column('nutrition_grade', sa.String(), nullable=True),
        sa.Column('nutriments_json', sa.String(), nullable=True),
        sa.Column('health_score', sa.Float(), nullable=True),
        sa.Column('health_category', sa.String(), nullable=True),
        sa.Column('source_detail', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('barcode')
    )

    # 22. Recommendation History
    op.create_table(
        'recommendation_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('recommendation_type', sa.String(), nullable=False),
        sa.Column('recommended_item_code', sa.String(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 23. Health Scores
    op.create_table(
        'health_scores',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('item_type', sa.String(), nullable=False),
        sa.Column('item_code', sa.String(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 24. Analytics
    op.create_table(
        'analytics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('metric_name', sa.String(), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('recorded_at', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 25. Generated Meal Plans
    op.create_table(
        'generated_meal_plans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_date', sa.Date(), nullable=False),
        sa.Column('breakfast_recipe_code', sa.String(), nullable=True),
        sa.Column('lunch_recipe_code', sa.String(), nullable=True),
        sa.Column('dinner_recipe_code', sa.String(), nullable=True),
        sa.Column('snack_recipe_code', sa.String(), nullable=True),
        sa.Column('breakfast_servings', sa.Float(), server_default='1.0', nullable=True),
        sa.Column('lunch_servings', sa.Float(), server_default='1.0', nullable=True),
        sa.Column('dinner_servings', sa.Float(), server_default='1.0', nullable=True),
        sa.Column('snack_servings', sa.Float(), server_default='1.0', nullable=True),
        sa.Column('actual_calories', sa.Float(), nullable=True),
        sa.Column('actual_protein', sa.Float(), nullable=True),
        sa.Column('actual_carbs', sa.Float(), nullable=True),
        sa.Column('actual_fat', sa.Float(), nullable=True),
        sa.Column('adherence', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['breakfast_recipe_code'], ['recipes.recipe_code']),
        sa.ForeignKeyConstraint(['lunch_recipe_code'], ['recipes.recipe_code']),
        sa.ForeignKeyConstraint(['dinner_recipe_code'], ['recipes.recipe_code']),
        sa.ForeignKeyConstraint(['snack_recipe_code'], ['recipes.recipe_code']),
        sa.PrimaryKeyConstraint('id')
    )

    # 26. Unit Conversions
    op.create_table(
        'unit_conversions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('food_item', sa.String(), nullable=False),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('gram_weight', sa.Float(), nullable=False),
        sa.Column('source', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_unit_conversions_food_item', 'unit_conversions', ['food_item'], unique=False)

    # 27. Homely Meals
    op.create_table(
        'homely_meals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('creator_id', sa.Integer(), nullable=True),
        sa.Column('is_community', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('status', sa.String(), server_default='pending', nullable=True),
        sa.Column('popularity', sa.Integer(), server_default='0', nullable=True),
        sa.Column('cuisine', sa.String(), nullable=True),
        sa.Column('region', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_homely_meals_name', 'homely_meals', ['name'], unique=False)

    # 28. Homely Meal Ingredients
    op.create_table(
        'homely_meal_ingredients',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('meal_id', sa.Integer(), nullable=False),
        sa.Column('ingredient_name', sa.String(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('gram_weight', sa.Float(), nullable=False),
        sa.Column('food_code', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['meal_id'], ['homely_meals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 29. Homely Meal Nutrition
    op.create_table(
        'homely_meal_nutrition',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('meal_id', sa.Integer(), nullable=False),
        sa.Column('energy_kcal', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('protein_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('carb_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('fat_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('fibre_g', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('sodium_mg', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('sugar_g', sa.Float(), server_default='0.0', nullable=True),
        sa.ForeignKeyConstraint(['meal_id'], ['homely_meals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('meal_id')
    )

    # 30. Homely Meal Versions
    op.create_table(
        'homely_meal_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('meal_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('edited_by', sa.Integer(), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['edited_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['meal_id'], ['homely_meals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 31. Homely Meal Reviews
    op.create_table(
        'homely_meal_reviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('meal_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['meal_id'], ['homely_meals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # 32. Homely Meal Tags
    op.create_table(
        'homely_meal_tags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('meal_id', sa.Integer(), nullable=False),
        sa.Column('tag', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['meal_id'], ['homely_meals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 33. Search History
    op.create_table(
        'search_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('query', sa.String(), nullable=False),
        sa.Column('searched_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 34. Settings
    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================
    # 5 New NutriX-Specific Microservice Tables
    # ==========================================

    # 35. User Adapters (MS1 YOLO Head Adapters)
    op.create_table(
        'user_adapters',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('weights_path', sa.Text(), nullable=False),
        sa.Column('adapter_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('base_model', sa.Text(), server_default='nutrix_yolo_custom.pt', nullable=False),
        sa.Column('num_classes', sa.Integer(), server_default='123', nullable=False),
        sa.Column('class_mappings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('training_images', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_trained_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_user_adapters_id', 'user_adapters', ['id'], unique=False)

    # 36. Audit Logs (MS1 + MS2 Trace & Observability)
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('service', sa.Text(), nullable=False),
        sa.Column('operation', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('input_hash', sa.Text(), nullable=True),
        sa.Column('output_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('s_faith_score', sa.Float(), nullable=True),
        sa.Column('flagged', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_id', 'audit_logs', ['id'], unique=False)

    # 37. Clinical Alerts (MS4 Guardian Alert Events)
    op.create_table(
        'clinical_alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.Text(), nullable=False),
        sa.Column('severity', sa.Text(), nullable=False),
        sa.Column('trigger_value', sa.Float(), nullable=True),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('resolved', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_clinical_alerts_id', 'clinical_alerts', ['id'], unique=False)

    # 38. Clinical Reports (MS4 Multi-Disciplinary Team Reports)
    op.create_table(
        'clinical_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=True),
        sa.Column('report_text', sa.Text(), nullable=False),
        sa.Column('nova_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('intervention', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['clinical_alerts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_clinical_reports_id', 'clinical_reports', ['id'], unique=False)

    # 39. System Prompt Registry (Versioned Prompts & Self-Healing Patch Store)
    op.create_table(
        'system_prompt_registry',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('prompt_key', sa.Text(), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('patched_by', sa.Text(), server_default='human', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prompt_key')
    )
    op.create_index('ix_system_prompt_registry_id', 'system_prompt_registry', ['id'], unique=False)

    # ==========================================
    # PostgreSQL Trigger for Live Macro Streaming
    # ==========================================
    op.execute("""
    CREATE OR REPLACE FUNCTION notify_macro_update()
    RETURNS TRIGGER AS $$
    DECLARE
        payload JSONB;
    BEGIN
        SELECT jsonb_build_object(
            'user_id',  NEW.user_id,
            'date',     CURRENT_DATE::TEXT,
            'calories', COALESCE(SUM(calories), 0),
            'protein',  COALESCE(SUM(protein), 0),
            'carbs',    COALESCE(SUM(carbs), 0),
            'fat',      COALESCE(SUM(fat), 0)
        ) INTO payload
        FROM meal_logs
        WHERE user_id = NEW.user_id
          AND log_date = CURRENT_DATE;

        PERFORM pg_notify('macro_update', payload::TEXT);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    DROP TRIGGER IF EXISTS trg_macro_update ON meal_logs;
    CREATE TRIGGER trg_macro_update
    AFTER INSERT OR UPDATE ON meal_logs
    FOR EACH ROW EXECUTE FUNCTION notify_macro_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_macro_update ON meal_logs;")
    op.execute("DROP FUNCTION IF EXISTS notify_macro_update();")

    tables = [
        "system_prompt_registry", "clinical_reports", "clinical_alerts", "audit_logs", "user_adapters",
        "settings", "search_history", "homely_meal_tags", "homely_meal_reviews", "homely_meal_versions",
        "homely_meal_nutrition", "homely_meal_ingredients", "homely_meals", "unit_conversions",
        "generated_meal_plans", "analytics", "health_scores", "recommendation_history", "barcode_cache",
        "recipe_nutrition", "recipe_ingredients", "servings", "recipes",
        "food_nutrients", "foods", "goals", "user_preferences",
        "profiles", "users"
    ]
    for table in tables:
        op.drop_table(table)
