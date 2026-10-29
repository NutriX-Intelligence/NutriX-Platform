# NOTE: converted from the standalone MS3 app/main.py. Handler bodies are unchanged; routes are registered on
# two DualRouters (public + authenticated) that serve every path both as /api/v1/... and as the legacy path.
import os
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status, UploadFile, File, Form
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from shared.db import get_db
from shared import clock
from shared.macro_sync import sync_daily_macros
from shared.redis_client import get_daily_macros
from ms3_user.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    verify_google_id_token,
)
from shared import models
from ms3_user import schemas
from ms3_user.services.nutrition_engine import NutritionEngine, normalize_goal
from ms3_user.services.recommendation_engine import RecommendationEngine
from ms3_user.services.optimization_engine import OptimizationEngine
from ms3_user.services.adaptive_planner import AdaptivePlanner
from ms3_user.services.ingredient_matcher import (
    compute_ingredient_match_score,
    normalise,
    clean_ingredient,
    fuzzy_match_ingredient,
)
from ms3_user.services.health_scorer import HealthScorer
from ms3_user.services.recipe_ranker import compute_final_score
from ms3_user.services.explanation_engine import ExplanationEngine
from ms3_user.services.classification_engine import ClassificationEngine
from ms3_user.services.barcode_service import BarcodeService
from ms3_user.services.ocr_engine import OCREngine
from ms3_user.services.analytics_engine import AnalyticsEngine
from ms3_user import schemas_recipes
from ms3_user.services import homely_meals_engine
from ms3_user.services import gemini_client
from ms3_user.services import ai_text
from ms3_user.services import recipe_nutrition
from ms3_user.services import live_stream

from fastapi.responses import JSONResponse, StreamingResponse
from pathlib import Path

from ms3_user.deps import get_current_user, enforce_ownership
from ms3_user.routing import DualRouter

public_router = APIRouter()
api_router = APIRouter(dependencies=[Depends(enforce_ownership)])
public = DualRouter(public_router)
api = DualRouter(api_router)


def format_user_profile(user: models.User) -> Dict[str, Any]:
    # Compute targets using NutritionEngine
    targets = NutritionEngine.calculate_targets(
        age=user.age or 25,
        gender=user.gender or "male",
        height=user.height or 170.0,
        weight=user.weight or 70.0,
        activity_level=user.activity_level or "sedentary",
        goal=user.goal or "maintenance"
    )
    
    # Get preferences
    diet_type = "Non-Vegetarian"
    likes_list = []
    allergies_list = []
    dislikes_list = []
    for p in (user.preferences or []):
        t = (p.preference_type or "").lower()
        val = (p.value or "").strip()
        if t == "diet_type":
            diet_type = val
        elif t == "like":
            likes_list.append(val)
        elif t == "allergy":
            allergies_list.append(val)
        elif t == "dislike":
            dislikes_list.append(val)

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "age": user.age or 25,
        "gender": user.gender or "male",
        "height": user.height or 170.0,
        "weight": user.weight or 70.0,
        "activity_level": user.activity_level or "sedentary",
        "goal": user.goal or "maintenance",
        "target_calories": user.target_calories or targets.get("target_calories") or 2000.0,
        "target_protein": user.target_protein or targets.get("target_protein_g") or 120.0,
        "target_carbs": user.target_carbs or targets.get("target_carbs_g") or 250.0,
        "target_fat": user.target_fat or targets.get("target_fat_g") or 60.0,
        "water_target_ml": user.water_target_ml or targets.get("water_target_ml") or 2500.0,
        "bmi": targets.get("bmi"),
        "bmi_status": targets.get("bmi_status"),
        "bmr": targets.get("bmr"),
        "tdee": targets.get("tdee"),
        "created_at": user.created_at,
        "diet_type": diet_type,
        "likes": ", ".join(likes_list),
        "allergies": ", ".join(allergies_list),
        "dislikes": ", ".join(dislikes_list),
        "is_onboarded": bool(user.is_onboarded) if getattr(user, "is_onboarded", None) is not None else False,
    }

@public.post("/api/auth/register", response_model=schemas.AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(req: schemas.UserRegisterRequest, db: Session = Depends(get_db)):
    if not req.name or not req.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full Name is required."
        )
    if not req.email or "@" not in req.email or "." not in req.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address."
        )
    if not req.password or len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )

    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == req.email.strip().lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Please sign in instead."
        )

    # Compute targets using NutritionEngine
    targets = NutritionEngine.calculate_targets(
        age=req.age,
        gender=req.gender,
        height=req.height,
        weight=req.weight,
        activity_level=req.activity_level,
        goal=req.goal
    )

    # Create new user
    user = models.User(
        name=req.name.strip(),
        email=req.email.strip().lower(),
        hashed_password=hash_password(req.password),
        is_onboarded=False,
        age=req.age,
        gender=req.gender,
        height=req.height,
        weight=req.weight,
        activity_level=req.activity_level,
        goal=req.goal,
        target_calories=targets["target_calories"],
        target_protein=targets["target_protein_g"],
        target_carbs=targets["target_carbs_g"],
        target_fat=targets["target_fat_g"],
        water_target_ml=req.water_target_ml or targets["water_target_ml"]
    )
    db.add(user)
    db.flush() # Eagerly generate ID

    # Save preferences if provided
    if req.preferences:
        for pref in req.preferences:
            db_pref = models.UserPreference(
                user_id=user.id,
                preference_type=pref.preference_type,
                value=pref.value
            )
            db.add(db_pref)

    db.commit()
    db.refresh(user)

    # Generate JWT
    token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(data=token_data)

    user_profile = format_user_profile(user)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "is_new_user": True,
        "user": user_profile
    }

@public.post("/api/auth/login", response_model=schemas.AuthTokenResponse)
def login_user(req: schemas.UserLoginRequest, db: Session = Depends(get_db)):
    if not req.email or not req.email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is required."
        )
    if not req.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required."
        )

    user = db.query(models.User).filter(models.User.email == req.email.strip().lower()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Please sign up or create an account."
        )

    if not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please try again."
        )

    token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(data=token_data)

    user_profile = format_user_profile(user)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_profile
    }

@public.post("/api/auth/google", response_model=schemas.AuthTokenResponse)
async def login_google(req: schemas.GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        payload = await verify_google_id_token(req.id_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google authentication failed: {str(e)}"
        )

    email = payload.get("email")
    name = payload.get("name", "Google User")
    google_id = payload.get("sub")
    picture = payload.get("picture")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID token does not contain a valid email address."
        )

    # Check if user exists
    user = db.query(models.User).filter(models.User.email == email).first()
    is_new_user = False
    if not user:
        is_new_user = True
        # Create a new user with default metrics and is_onboarded=False
        targets = NutritionEngine.calculate_targets(
            age=25,
            gender="male",
            height=170.0,
            weight=70.0,
            activity_level="sedentary",
            goal="maintenance"
        )
        user = models.User(
            name=name,
            email=email,
            google_id=google_id,
            avatar_url=picture,
            is_onboarded=False,
            age=25,
            gender="male",
            height=170.0,
            weight=70.0,
            activity_level="sedentary",
            goal="maintenance",
            target_calories=targets["target_calories"],
            target_protein=targets["target_protein_g"],
            target_carbs=targets["target_carbs_g"],
            target_fat=targets["target_fat_g"]
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update google_id and avatar if not set
        updated = False
        if not user.google_id:
            user.google_id = google_id
            updated = True
        if picture and not user.avatar_url:
            user.avatar_url = picture
            updated = True
        if updated:
            db.commit()
            db.refresh(user)

    token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(data=token_data)

    user_profile = format_user_profile(user)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "is_new_user": is_new_user,
        "user": user_profile
    }

@api.get("/api/auth/me", response_model=schemas.UserProfileResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return format_user_profile(current_user)

@api.post("/api/auth/me", response_model=schemas.UserProfileResponse)
def post_me(current_user: models.User = Depends(get_current_user)):
    return format_user_profile(current_user)

@public.post("/api/auth/reset-password")
def reset_password(req: schemas.PasswordResetRequest, db: Session = Depends(get_db)):
    import logging
    logger = logging.getLogger("auth_reset")
    user = db.query(models.User).filter(models.User.email == req.email).first()
    if not user:
        logger.warning(f"Password reset requested for non-existent email: {req.email}")
        return {"status": "success", "message": "If the email exists, a password reset link has been simulated."}

    import uuid
    reset_token = str(uuid.uuid4())
    simulated_link = f"http://localhost:8000/api/auth/reset-confirm?token={reset_token}&email={user.email}"
    
    from ms3_user.services.auth_service import IS_DEV
    if IS_DEV:  # never expose reset links outside development
        print("------------------------------------------------------------")
        print(f"SIMULATED EMAIL: Password reset requested for {user.name} ({user.email})")
        print(f"Simulated Reset Link: {simulated_link}")
        print("------------------------------------------------------------")
        logger.info(f"Simulated reset link for {user.email}: {simulated_link}")

    return {"status": "success", "message": "Password reset link has been simulated in console logs."}

@api.get("/api/search-history", response_model=List[schemas.SearchHistoryResponse])
def get_search_history(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    history = db.query(models.SearchHistory).filter(
        models.SearchHistory.user_id == current_user.id
    ).order_by(models.SearchHistory.searched_at.desc()).limit(50).all()
    return history

@api.post("/api/search-history", response_model=schemas.SearchHistoryResponse, status_code=status.HTTP_201_CREATED)
def add_search_history(req: schemas.SearchHistoryCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_history = models.SearchHistory(
        user_id=current_user.id,
        query=req.query
    )
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    return db_history

@api.get("/api/settings", response_model=List[schemas.SettingsResponse])
def get_settings(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_settings = db.query(models.Settings).filter(
        models.Settings.user_id == current_user.id
    ).all()
    return user_settings

@api.put("/api/settings", response_model=schemas.SettingsResponse)
def update_settings(req: schemas.SettingsUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_setting = db.query(models.Settings).filter(
        models.Settings.user_id == current_user.id,
        models.Settings.key == req.key
    ).first()

    if db_setting:
        db_setting.value = req.value
    else:
        db_setting = models.Settings(
            user_id=current_user.id,
            key=req.key,
            value=req.value
        )
        db.add(db_setting)
    
    db.commit()
    db.refresh(db_setting)
    return db_setting

@api.get("/users/{user_id}/targets", response_model=schemas.UserProfileResponse)
def get_user_targets(user_id: int, db: Session = Depends(get_db)):
    """Get user profile with targets."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    
    # Compute targets on the fly using NutritionEngine
    targets = NutritionEngine.calculate_targets(
        age=user.age,
        gender=user.gender,
        height=user.height,
        weight=user.weight,
        activity_level=user.activity_level,
        goal=user.goal
    )

    # Get preferences
    diet_type = "Non-Vegetarian"
    likes_list = []
    allergies_list = []
    dislikes_list = []
    for p in user.preferences:
        t = p.preference_type.lower()
        val = p.value.strip()
        if t == "diet_type":
            diet_type = val
        elif t == "like":
            likes_list.append(val)
        elif t == "allergy":
            allergies_list.append(val)
        elif t == "dislike":
            dislikes_list.append(val)

    response_data = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "age": user.age,
        "gender": user.gender,
        "height": user.height,
        "weight": user.weight,
        "activity_level": user.activity_level,
        "goal": user.goal,
        "target_calories": user.target_calories,
        "target_protein": user.target_protein,
        "target_carbs": user.target_carbs,
        "target_fat": user.target_fat,
        "bmi": targets.get("bmi"),
        "bmi_status": targets.get("bmi_status"),
        "bmr": targets.get("bmr"),
        "tdee": targets.get("tdee"),
        "created_at": user.created_at,
        "diet_type": diet_type,
        "likes": ", ".join(likes_list),
        "allergies": ", ".join(allergies_list),
        "dislikes": ", ".join(dislikes_list),
    }
    return response_data

@api.get("/users/{user_id}/weight-history", response_model=List[schemas.WeightLogEntry])
def get_weight_history(user_id: int, db: Session = Depends(get_db)):
    """Get weight log history for a user."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    logs = db.query(models.WeightLog).filter(
        models.WeightLog.user_id == user_id
    ).order_by(models.WeightLog.logged_at.desc()).limit(90).all()
    return logs

@api.get("/users/{user_id}/meal-plans", response_model=List[schemas.MealPlanHistoryItem])
def get_meal_plan_history(user_id: int, db: Session = Depends(get_db)):
    """Get meal plan history for a user."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    plans = db.query(models.GeneratedMealPlan).filter(
        models.GeneratedMealPlan.user_id == user_id
    ).order_by(models.GeneratedMealPlan.plan_date.desc()).limit(30).all()
    
    result = []
    for p in plans:
        item = schemas.MealPlanHistoryItem(
            id=p.id,
            plan_date=p.plan_date,
            actual_calories=p.actual_calories,
            actual_protein=p.actual_protein,
            actual_carbs=p.actual_carbs,
            actual_fat=p.actual_fat,
            adherence=p.adherence
        )
        if p.breakfast_recipe:
            item.breakfast_recipe_name = p.breakfast_recipe.recipe_name
        if p.lunch_recipe:
            item.lunch_recipe_name = p.lunch_recipe.recipe_name
        if p.dinner_recipe:
            item.dinner_recipe_name = p.dinner_recipe.recipe_name
        if p.snack_recipe:
            item.snack_recipe_name = p.snack_recipe.recipe_name
        result.append(item)
    
    return result

@api.post("/calculate-profile", response_model=schemas.UserProfileResponse, status_code=status.HTTP_201_CREATED)
def calculate_profile(profile_in: schemas.UserProfileCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Calculate target nutrients based on user metrics and save/update the user profile."""
    if (profile_in.email or "").strip().lower() != (current_user.email or "").lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own profile.")
    # Compute targets using NutritionEngine
    targets = NutritionEngine.calculate_targets(
        age=profile_in.age,
        gender=profile_in.gender,
        height=profile_in.height,
        weight=profile_in.weight,
        activity_level=profile_in.activity_level,
        goal=profile_in.goal
    )

    water_target = profile_in.water_target_ml or targets["water_target_ml"]

    # Check if user already exists
    user = db.query(models.User).filter(models.User.email == profile_in.email).first()
    if user:
        # Update existing user profile
        user.name = profile_in.name
        user.age = profile_in.age
        user.gender = profile_in.gender
        user.height = profile_in.height
        user.weight = profile_in.weight
        user.activity_level = profile_in.activity_level
        user.goal = profile_in.goal
        user.target_calories = targets["target_calories"]
        user.target_protein = targets["target_protein_g"]
        user.target_carbs = targets["target_carbs_g"]
        user.target_fat = targets["target_fat_g"]
        user.water_target_ml = water_target
        user.is_onboarded = True
        
        # Delete old preferences to replace them
        db.query(models.UserPreference).filter(models.UserPreference.user_id == user.id).delete()
    else:
        # Create new user
        user = models.User(
            name=profile_in.name,
            email=profile_in.email,
            is_onboarded=True,
            age=profile_in.age,
            gender=profile_in.gender,
            height=profile_in.height,
            weight=profile_in.weight,
            activity_level=profile_in.activity_level,
            goal=profile_in.goal,
            target_calories=targets["target_calories"],
            target_protein=targets["target_protein_g"],
            target_carbs=targets["target_carbs_g"],
            target_fat=targets["target_fat_g"],
            water_target_ml=water_target
        )
        db.add(user)
        db.flush() # Eagerly generate ID

    # Save preferences if provided
    if profile_in.preferences:
        for pref in profile_in.preferences:
            db_pref = models.UserPreference(
                user_id=user.id,
                preference_type=pref.preference_type,
                value=pref.value
            )
            db.add(db_pref)

    db.commit()
    db.refresh(user)

    return format_user_profile(user)

@api.post("/recommend-foods", response_model=List[schemas.RankedFoodItem])
def recommend_foods(req: schemas.RecommendFoodsRequest, response: Response, db: Session = Depends(get_db)):
    """Get ranked recipes customized to user targets, allergies, likes, and dislikes."""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"User with ID {req.user_id} not found."
        )
    
    limit = req.limit or 300
    offset = req.offset or 0
    page, total = RecommendationEngine.get_recommendations(
        db=db,
        user_id=req.user_id,
        limit=limit,
        query_str=req.query,
        category=req.category,
        cuisine=req.cuisine,
        max_cooking_time=req.max_cooking_time,
        brand=req.brand,
        diet_filter=req.diet_filter,
        offset=offset,
        exclude_fast_food=bool(req.exclude_fast_food),
        return_total=True,
    )
    # the body stays a plain list (existing clients keep working); paging info travels in headers
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page-Offset"] = str(offset)
    response.headers["X-Has-More"] = "true" if offset + len(page) < total else "false"
    import logging as _logging
    _logging.getLogger("ms3.foods").info(
        "foods/recommend user=%s limit=%s offset=%s diet=%s category=%s cuisine=%s brand=%s q=%r exclude_ff=%s -> %d of %d",
        req.user_id, limit, offset, req.diet_filter, req.category, req.cuisine, req.brand, req.query,
        bool(req.exclude_fast_food), len(page), total)
    return page

@api.get("/api/fast-food/chains", response_model=List[schemas.FastFoodChainSummary])
def get_fast_food_chains(db: Session = Depends(get_db)):
    """Get summary statistics for all fast food chains with dietary breakdown."""
    brand_icons = {
        "Domino's": "🍕",
        "McDonald's": "🍔",
        "Subway": "🥪",
        "Burger King": "👑",
        "KFC": "🍗",
        "Pizza Hut": "🍕",
        "Starbucks": "☕",
        "Taco Bell": "🌮"
    }

    results = []
    for brand, icon in brand_icons.items():
        recipes = db.query(models.Recipe).options(
            joinedload(models.Recipe.nutrition)
        ).filter(models.Recipe.brand == brand).all()

        if not recipes:
            continue

        total = len(recipes)
        veg_cnt = sum(1 for r in recipes if r.dietary_tag in ("Vegetarian", "Vegan", "Jain"))
        non_veg_cnt = sum(1 for r in recipes if r.dietary_tag == "Non-Vegetarian")
        jain_cnt = sum(1 for r in recipes if r.dietary_tag == "Jain")
        vegan_cnt = sum(1 for r in recipes if r.dietary_tag in ("Vegan", "Jain"))
        
        cals = [r.nutrition.energy_kcal for r in recipes if r.nutrition and r.nutrition.energy_kcal]
        avg_cal = round(sum(cals) / len(cals), 1) if cals else 0.0

        cats = sorted(list(set(
            r.category for r in recipes if r.category
        )))

        results.append(schemas.FastFoodChainSummary(
            brand=brand,
            icon=icon,
            total_items=total,
            veg_count=veg_cnt,
            non_veg_count=non_veg_cnt,
            jain_count=jain_cnt,
            vegan_count=vegan_cnt,
            avg_calories=avg_cal,
            categories=cats
        ))

    return results

@api.get("/api/fast-food/grouped", response_model=List[schemas.FastFoodGroup])
def get_fast_food_grouped(
    q: Optional[str] = None,
    brand: Optional[str] = None,
    diet_filter: Optional[str] = None,
    category: Optional[str] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Search and group fast food items by brand and category sections.
    Supports user preference (veg/non-veg/jain/vegan), brand search ('dominos'), and category filtering.
    """
    effective_diet = diet_filter
    if (not effective_diet or effective_diet.lower() in ("all", "any")) and user_id:
        user_prof = db.query(models.Profile).filter(models.Profile.user_id == user_id).first()
        if user_prof and user_prof.diet_type:
            effective_diet = user_prof.diet_type

    base_query = db.query(models.Recipe).options(
        joinedload(models.Recipe.nutrition),
        joinedload(models.Recipe.servings)
    ).filter(models.Recipe.recipe_code.like("FF_%"))

    # Dietary filter
    if effective_diet and effective_diet.lower() not in ("all", "any"):
        d_low = effective_diet.lower()
        if "jain" in d_low:
            base_query = base_query.filter(models.Recipe.dietary_tag == "Jain")
        elif "vegan" in d_low:
            base_query = base_query.filter(models.Recipe.dietary_tag.in_(["Vegan", "Jain"]))
        elif "vegetarian" in d_low and "non" not in d_low:
            base_query = base_query.filter(models.Recipe.dietary_tag.in_(["Vegetarian", "Vegan", "Jain"]))
        elif "non" in d_low:
            base_query = base_query.filter(models.Recipe.dietary_tag == "Non-Vegetarian")

    # Category filter
    if category and category.lower() != "all":
        base_query = base_query.filter(models.Recipe.category.ilike(f"%{category}%"))

    # Brand filter with alias resolution
    brand_aliases = {
        "domino": "Domino's",
        "dominos": "Domino's",
        "domino's": "Domino's",
        "mcdonald": "McDonald's",
        "mcdonalds": "McDonald's",
        "mcdonald's": "McDonald's",
        "mcd": "McDonald's",
        "burger king": "Burger King",
        "burgerking": "Burger King",
        "bk": "Burger King",
        "subway": "Subway",
        "kfc": "KFC",
        "kentucky": "KFC",
        "pizza hut": "Pizza Hut",
        "pizzahut": "Pizza Hut",
        "starbucks": "Starbucks",
        "sbux": "Starbucks",
        "taco bell": "Taco Bell",
        "tacobell": "Taco Bell"
    }

    if brand and brand.lower() != "all":
        canon_brand = brand_aliases.get(brand.strip().lower(), brand)
        base_query = base_query.filter(
            or_(
                models.Recipe.brand.ilike(f"%{canon_brand}%"),
                models.Recipe.cuisine.ilike(f"%{canon_brand}%")
            )
        )

    # Search query
    if q and q.strip():
        search_str = q.strip().lower()
        search_no_punct = search_str.replace("'", "").replace("-", " ")
        canon_from_q = brand_aliases.get(search_str) or brand_aliases.get(search_no_punct)

        if canon_from_q:
            base_query = base_query.filter(
                or_(
                    models.Recipe.brand == canon_from_q,
                    models.Recipe.brand.ilike(f"%{canon_from_q}%"),
                    models.Recipe.recipe_name.ilike(f"%{search_str}%")
                )
            )
        else:
            words = search_str.split()
            word_clauses = []
            for w in words:
                w_canon = brand_aliases.get(w.replace("'", ""))
                if w_canon:
                    word_clauses.append(models.Recipe.brand == w_canon)
                else:
                    word_clauses.append(
                        or_(
                            models.Recipe.recipe_name.ilike(f"%{w}%"),
                            models.Recipe.brand.ilike(f"%{w}%"),
                            models.Recipe.instructions.ilike(f"%{w}%")
                        )
                    )
            base_query = base_query.filter(
                or_(
                    models.Recipe.recipe_name.ilike(f"%{search_str}%"),
                    models.Recipe.brand.ilike(f"%{search_str}%"),
                    models.Recipe.instructions.ilike(f"%{search_str}%"),
                    and_(*word_clauses)
                )
            )

    all_recipes = base_query.all()

    # Group by brand
    from collections import defaultdict
    brand_map = defaultdict(list)
    for r in all_recipes:
        b_name = r.brand or "Fast Food"
        brand_map[b_name].append(r)

    groups = []
    ordered_brands = ["Domino's", "McDonald's", "Subway", "Burger King", "KFC", "Pizza Hut", "Starbucks", "Taco Bell"]
    remaining_brands = [b for b in brand_map.keys() if b not in ordered_brands]
    all_brand_keys = [b for b in ordered_brands if b in brand_map] + remaining_brands

    for b in all_brand_keys:
        b_recipes = brand_map[b]
        if not b_recipes:
            continue

        veg_count = sum(1 for r in b_recipes if r.dietary_tag in ("Vegetarian", "Vegan", "Jain"))
        non_veg_count = sum(1 for r in b_recipes if r.dietary_tag == "Non-Vegetarian")
        jain_count = sum(1 for r in b_recipes if r.dietary_tag == "Jain")
        vegan_count = sum(1 for r in b_recipes if r.dietary_tag in ("Vegan", "Jain"))

        cals = [r.nutrition.energy_kcal for r in b_recipes if r.nutrition and r.nutrition.energy_kcal]
        min_c = min(cals) if cals else 0.0
        max_c = max(cals) if cals else 0.0

        sections_map = defaultdict(list)
        for r in b_recipes:
            sec_name = r.category
            if r.instructions and "(" in r.instructions and ")" in r.instructions:
                try:
                    sec_name = r.instructions.split("(")[1].split(")")[0].strip()
                except:
                    sec_name = r.category

            portion_desc = None
            if r.servings and r.servings.servings_unit:
                portion_desc = str(r.servings.servings_unit)
            elif r.servings and r.servings.size_of_servings:
                portion_desc = f"{int(r.servings.size_of_servings)}g"

            item_data = schemas.FastFoodItem(
                recipe_code=r.recipe_code,
                recipe_name=r.recipe_name,
                brand=b,
                category=r.category,
                sub_category=sec_name,
                dietary_tag=r.dietary_tag or "Vegetarian",
                portion_str=portion_desc or "1 serve",
                energy_kcal=round(r.nutrition.energy_kcal, 1) if r.nutrition else 0.0,
                protein_g=round(r.nutrition.protein_g, 1) if r.nutrition else 0.0,
                carb_g=round(r.nutrition.carb_g, 1) if r.nutrition else 0.0,
                fat_g=round(r.nutrition.fat_g, 1) if r.nutrition else 0.0,
                sugar_g=round(r.nutrition.freesugar_g, 1) if (r.nutrition and r.nutrition.freesugar_g) else 0.0,
                sodium_mg=round(r.nutrition.sodium_mg, 1) if (r.nutrition and r.nutrition.sodium_mg) else 0.0,
                fibre_g=round(r.nutrition.fibre_g, 1) if (r.nutrition and r.nutrition.fibre_g) else 0.0
            )
            sections_map[sec_name].append(item_data)

        sections = [
            schemas.FastFoodSection(section_name=s_name, items=s_items)
            for s_name, s_items in sorted(sections_map.items())
        ]

        groups.append(schemas.FastFoodGroup(
            brand=b,
            cuisine=b,
            item_count=len(b_recipes),
            veg_count=veg_count,
            non_veg_count=non_veg_count,
            jain_count=jain_count,
            vegan_count=vegan_count,
            min_calories=round(min_c, 1),
            max_calories=round(max_c, 1),
            sections=sections
        ))

    return groups


@api.post("/generate-meal-plan", response_model=schemas.MealPlanResponse)
def generate_meal_plan(req: schemas.GenerateMealPlanRequest, db: Session = Depends(get_db)):
    """Generate a daily meal plan satisfying targets using OR-Tools Linear Programming."""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"User with ID {req.user_id} not found."
        )

    plan_date = req.plan_date or clock.today()
    
    # Run MIP solver to find optimal plan
    plan = OptimizationEngine.generate_daily_plan(
        db=db, 
        user_id=req.user_id, 
        tolerance=req.tolerance or 0.15,
        preference=req.preference or "balanced",
        meal_cuisines=req.meal_cuisines
    )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not generate a feasible meal plan satisfying nutrient targets. Try widening the tolerance."
        )

    # Save generated plan to database
    # Deleting any existing plan for the same day first to override
    db.query(models.GeneratedMealPlan).filter(
        models.GeneratedMealPlan.user_id == req.user_id,
        models.GeneratedMealPlan.plan_date == plan_date
    ).delete()

    db_plan = models.GeneratedMealPlan(
        user_id=req.user_id,
        plan_date=plan_date,
        breakfast_recipe_code=plan["meals"]["Breakfast"]["recipe_code"],
        lunch_recipe_code=plan["meals"]["Lunch"]["recipe_code"],
        dinner_recipe_code=plan["meals"]["Dinner"]["recipe_code"],
        snack_recipe_code=plan["meals"]["Snack"]["recipe_code"],
        breakfast_servings=1.0,
        lunch_servings=1.0,
        dinner_servings=1.0,
        snack_servings=1.0,
        actual_calories=plan["totals"]["calories"],
        actual_protein=plan["totals"]["protein_g"],
        actual_carbs=plan["totals"]["carbs_g"],
        actual_fat=plan["totals"]["fat_g"]
    )
    db.add(db_plan)
    db.commit()

    return {
        "user_id": req.user_id,
        "plan_date": plan_date,
        "meals": plan["meals"],
        "totals": plan["totals"],
        "targets": plan["targets"],
        "tolerance_used": plan["tolerance_used"]
    }

# =====================================================================
# RECIPE INTELLIGENCE ENGINE ENDPOINTS
# =====================================================================


@api.get("/recipes/top", response_model=schemas_recipes.TopRecipesResponse)
def get_top_recipes(
    limit: int = 10,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """GET /recipes/top — Return top-rated recipes by health score."""
    from sqlalchemy.orm import joinedload

    query = db.query(models.Recipe).options(
        joinedload(models.Recipe.nutrition),
    )

    if category:
        query = query.filter(models.Recipe.category == category)

    recipes = query.all()

    scored = []
    for r in recipes:
        if not r.nutrition or not r.nutrition.energy_kcal:
            continue
        hs, hcat, _ = HealthScorer.score_from_per_serving(r.nutrition)
        d_tag = RecommendationEngine.get_dietary_tag(r)
        scored.append({
            "recipe_code": r.recipe_code,
            "recipe_name": r.recipe_name,
            "category": r.category,
            "cuisine": r.cuisine,
            "difficulty": r.difficulty,
            "cooking_time_minutes": r.cooking_time_minutes,
            "dietary_tag": d_tag,
            "health_score": hs,
            "health_category": hcat,
            "calories": r.nutrition.energy_kcal,
            "protein_g": r.nutrition.protein_g,
            "carbs_g": r.nutrition.carb_g,
            "fat_g": r.nutrition.fat_g,
        })

    scored.sort(key=lambda x: x["health_score"], reverse=True)
    return {"recipes": scored[:limit], "total": len(scored)}


@api.get("/recipes/search", response_model=List[schemas_recipes.RecipeSearchResult])
def search_recipes(
    q: str,
    category: Optional[str] = None,
    cuisine: Optional[str] = None,
    max_results: int = 20,
    db: Session = Depends(get_db),
):
    """GET /recipes/search — Search recipes by name."""
    query = db.query(models.Recipe).filter(
        models.Recipe.recipe_name.ilike(f"%{q}%")
    )

    if category:
        query = query.filter(models.Recipe.category == category)
    if cuisine:
        query = query.filter(models.Recipe.cuisine.ilike(f"%{cuisine}%"))

    results = query.limit(max_results).all()

    return [
        {
            "recipe_code": r.recipe_code,
            "recipe_name": r.recipe_name,
            "category": r.category,
            "cuisine": r.cuisine,
            "dietary_tag": RecommendationEngine.get_dietary_tag(r),
        }
        for r in results
    ]


@api.get("/recipes/{recipe_code}", response_model=schemas_recipes.RecipeDetailResponse)
def get_recipe_detail(recipe_code: str, db: Session = Depends(get_db)):
    """GET /recipes/{id} — Get full details for a single recipe."""
    from sqlalchemy.orm import joinedload

    recipe = db.query(models.Recipe).options(
        joinedload(models.Recipe.nutrition),
        joinedload(models.Recipe.servings),
        joinedload(models.Recipe.ingredients),
    ).filter(models.Recipe.recipe_code == recipe_code).first()

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe '{recipe_code}' not found."
        )

    # Compute health score
    hs, hcat, hexp = HealthScorer.score_from_per_serving(recipe.nutrition)

    ingredients_list = []
    for ing in recipe.ingredients:
        ingredients_list.append({
            "ingredient_name": ing.ingredient_name,
            "food_name": ing.food_name,
            "amount": ing.amount,
            "unit": ing.unit,
        })

    nutrition_data = None
    if recipe.nutrition:
        nutrition_data = {
            "energy_kcal": recipe.nutrition.energy_kcal,
            "unit_serving_energy_kcal": recipe.nutrition.unit_serving_energy_kcal,
            "protein_g": recipe.nutrition.protein_g,
            "carb_g": recipe.nutrition.carb_g,
            "fat_g": recipe.nutrition.fat_g,
            "freesugar_g": recipe.nutrition.freesugar_g,
            "fibre_g": recipe.nutrition.fibre_g,
            "sodium_mg": recipe.nutrition.sodium_mg,
        }

    # Generate brief appetizing description
    desc = ""
    if recipe.instructions:
        first_sentence = recipe.instructions.split(".")[0].strip()
        if len(first_sentence) > 15:
            desc = first_sentence + "."
    if not desc or len(desc) < 15:
        ing_highlights = [i["food_name"] or i["ingredient_name"] for i in ingredients_list if i.get("food_name") or i.get("ingredient_name")][:3]
        ing_str = f" featuring {', '.join(ing_highlights)}" if ing_highlights else ""
        cal_val = nutrition_data.get('energy_kcal') if nutrition_data else 0
        cal_str = f" delivering ~{int(cal_val)} kcal" if cal_val else ""
        desc = f"A wholesome {recipe.cuisine or ''} {recipe.category or 'culinary specialty'}{ing_str}{cal_str} with balanced macro profile."

    return {
        "recipe_code": recipe.recipe_code,
        "recipe_name": recipe.recipe_name,
        "category": recipe.category,
        "cuisine": recipe.cuisine,
        "difficulty": recipe.difficulty,
        "cooking_time_minutes": recipe.cooking_time_minutes,
        "dietary_tag": RecommendationEngine.get_dietary_tag(recipe),
        "description": desc,
        "instructions": recipe.instructions,
        "primarysource": recipe.primarysource,
        "ingredients": ingredients_list,
        "nutrition": nutrition_data,
        "health_score": hs,
        "health_category": hcat,
    }


@api.post("/recipes/recommend", response_model=schemas_recipes.RecipeRecommendResponse)
def recommend_recipes_by_ingredients(
    req: schemas_recipes.RecipeRecommendRequest,
    db: Session = Depends(get_db),
):
    """
    POST /recipes/recommend — Find recipes you can cook with your ingredients.

    Uses fuzzy matching, health scoring, rule-based ranking, and
    deterministic explanations — no external AI APIs.
    """
    from sqlalchemy.orm import joinedload

    # Clean & normalise user ingredients
    user_ings = [clean_ingredient(i) for i in req.ingredients if i.strip()]
    user_ings = list(set(user_ings))  # deduplicate

    if not user_ings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide at least one valid ingredient."
        )

    aliases = {
        "bengali": ["bengal", "bengali", "machher", "kosha", "shorshe", "mishti", "sandesh", "pitha", "luchi", "cholar"],
        "rajasthani": ["rajasthan", "rajasthani", "baati", "gatte", "laal maas", "sangri", "kachori", "ghevar", "baati"],
        "gujarati": ["gujarat", "gujarati", "dhokla", "thepla", "khichdi", "khandvi", "undhiyu", "handvo", "farsan"],
        "maharashtrian": ["maharashtra", "maharashtrian", "marathi", "misal", "pavitra", "poha", "modak", "puran poli", "vada pav", "pitla"],
        "punjabi": ["punjab", "punjabi", "paneer butter", "tandoori", "chole", "bhature", "sarson", "makki", "dal makhani", "amritsari"],
        "south indian": ["south indian", "dosa", "idli", "sambar", "rasam", "uttapam", "hyderabadi", "kerala", "chettinad", "bisi bele", "appam", "vada", "payasam"],
        "north indian": ["north indian", "paneer", "dal makhani", "korma", "naan", "tikka", "kofta", "biryani", "paratha"],
        "mughlai": ["mughlai", "biryani", "korma", "pasanda", "shahi", "nargisi", "nihari"],
        "kashmiri": ["kashmiri", "rogan josh", "dum aloo", "yakhni", "kahwa"],
        "chinese": ["chinese", "indo-chinese", "hakka", "manchurian", "chow mein", "schezwan", "noodle", "fried rice", "dim sum", "congee", "bao", "sichuan"],
        "indo-chinese": ["chinese", "indo-chinese", "hakka", "manchurian", "chow mein", "schezwan", "noodle", "fried rice"],
        "italian": ["italian", "pasta", "pizza", "risotto", "spaghetti", "bruschetta", "cornetto", "frittata", "arancini", "pesto", "lasagna"],
        "japanese": ["japanese", "sushi", "ramen", "teriyaki", "tempura", "miso", "udon", "donburi", "matcha", "bento", "soba"],
        "mexican": ["mexican", "taco", "burrito", "quesadilla", "enchilada", "fajita", "guacamole", "salsa", "nacho", "chili"],
        "continental": ["continental", "steak", "roast", "soup", "salad", "bake", "grill", "stew"],
        "asian": ["asian", "thai", "japanese", "korean", "vietnamese", "chinese"],
    }

    # High-Performance SQL Query with SQL-level Pre-filtering
    from sqlalchemy import or_
    query = db.query(models.Recipe).options(
        joinedload(models.Recipe.ingredients),
        joinedload(models.Recipe.nutrition),
    )

    # 1. SQL Cuisine Pre-Filter
    if req.cuisine:
        c_lower = req.cuisine.lower()
        sub_kws = aliases.get(c_lower, [c_lower])
        c_conds = [models.Recipe.cuisine.ilike(f"%{kw}%") | models.Recipe.recipe_name.ilike(f"%{kw}%") for kw in sub_kws]
        query = query.filter(or_(*c_conds))

    # 2. SQL Max Cooking Time Filter
    if req.max_cooking_time is not None:
        query = query.filter(models.Recipe.cooking_time_minutes <= req.max_cooking_time)

    # 3. SQL Candidate Pre-Filter for fast ingredient matching (when no cuisine constraint)
    if not req.cuisine and user_ings:
        ing_conds = [
            models.RecipeIngredient.ingredient_name.ilike(f"%{t}%") | models.RecipeIngredient.food_name.ilike(f"%{t}%")
            for t in user_ings if len(t) >= 2
        ]
        name_conds = [
            models.Recipe.recipe_name.ilike(f"%{t}%")
            for t in user_ings if len(t) >= 2
        ]
        candidate_codes = set()
        if ing_conds:
            for row in db.query(models.RecipeIngredient.recipe_code).filter(or_(*ing_conds)).distinct().limit(250).all():
                if row[0]:
                    candidate_codes.add(row[0])
        if name_conds:
            for row in db.query(models.Recipe.recipe_code).filter(or_(*name_conds)).distinct().limit(100).all():
                if row[0]:
                    candidate_codes.add(row[0])
        
        if candidate_codes:
            query = query.filter(models.Recipe.recipe_code.in_(list(candidate_codes)))

    recipes = query.limit(300).all()

    # Apply remaining Python rule filters
    filtered_recipes = []
    for r in recipes:
        # Diet type filter
        if req.diet_type:
            dt = req.diet_type.lower()
            if "jain" in dt and not RecommendationEngine.is_jain(r):
                continue
            elif "vegan" in dt and not RecommendationEngine.is_vegan(r):
                continue
            elif "eggetarian" in dt and not RecommendationEngine.is_eggetarian(r):
                continue
            elif "vegetarian" in dt and "non" not in dt and not RecommendationEngine.is_vegetarian(r):
                continue

        # Max cooking time
        if req.max_cooking_time is not None:
            if req.max_cooking_time == 999 or req.max_cooking_time == 9999:
                if not r.cooking_time_minutes or r.cooking_time_minutes <= 60:
                    continue
            elif req.max_cooking_time > 0:
                if r.cooking_time_minutes and r.cooking_time_minutes > req.max_cooking_time:
                    continue

        # Exclude ingredient filter
        if req.exclude_ingredients:
            exclude_norm = [clean_ingredient(e) for e in req.exclude_ingredients]
            skip = False
            for ing in r.ingredients:
                ing_name = clean_ingredient(ing.food_name or ing.ingredient_name or "")
                for ex in exclude_norm:
                    if fuzzy_match_ingredient(ex, ing_name):
                        skip = True
                        break
                if skip:
                    break
            if skip:
                continue

        # Must have nutrition data to score
        if not r.nutrition or not r.nutrition.energy_kcal:
            continue

        filtered_recipes.append(r)

    # Score each recipe
    candidate_scores = []
    for r in filtered_recipes:
        # Get recipe ingredient names
        recipe_ing_names = []
        for ing in (r.ingredients or []):
            name = ing.food_name or ing.ingredient_name or ""
            if name:
                recipe_ing_names.append(clean_ingredient(name))
        recipe_ing_names = list(set(recipe_ing_names))

        # 1. Ingredient match
        match_score, matched, missing = compute_ingredient_match_score(
            user_ings, recipe_ing_names
        )

        if match_score == 0.0 or not matched:
            continue

        # 2. Health score
        hs, hcat, hexp = HealthScorer.score_from_per_serving(r.nutrition)

        # 3. Compute final ranking score
        final = compute_final_score(
            match_score, hs,
            r.nutrition.protein_g,
            r.nutrition.energy_kcal,
        )

        # Goal adjustment
        goal_mult = 1.0
        if req.goal:
            gl = req.goal.lower()
            if gl == "weight loss":
                if (r.nutrition.energy_kcal or 999) < 250:
                    goal_mult = 1.1
                else:
                    goal_mult = 0.85
            elif gl in ("muscle gain", "weight gain"):
                if (r.nutrition.protein_g or 0) >= 12:
                    goal_mult = 1.15
        final *= goal_mult

        d_tag = RecommendationEngine.get_dietary_tag(r)

        candidate_scores.append((
            final, r, match_score, matched, missing, hs, hcat, hexp, d_tag
        ))

    # Sort by final score descending
    candidate_scores.sort(key=lambda x: x[0], reverse=True)

    # Take top_n candidates and generate explanations only for the winners
    top_candidates = candidate_scores[:req.top_n]
    top = []

    for final, r, match_score, matched, missing, hs, hcat, hexp, d_tag in top_candidates:
        explanation = ExplanationEngine.generate(
            recipe_name=r.recipe_name,
            match_score=match_score,
            health_score=hs,
            health_category=hcat,
            health_explanation=hexp,
            matched_ingredients=matched,
            unmatched_ingredients=missing,
            user_ingredients=user_ings,
            protein_g=r.nutrition.protein_g,
            energy_kcal=r.nutrition.energy_kcal,
            carb_g=r.nutrition.carb_g,
            fat_g=r.nutrition.fat_g,
            goal=req.goal,
            cuisine=r.cuisine,
            difficulty=r.difficulty,
            dietary_tag=d_tag,
        )

        top.append({
            "recipe_code": r.recipe_code,
            "recipe_name": r.recipe_name,
            "category": r.category,
            "cuisine": r.cuisine,
            "difficulty": r.difficulty,
            "cooking_time_minutes": r.cooking_time_minutes,
            "dietary_tag": d_tag,
            "match_score": round(match_score, 2),
            "health_score": round(hs, 2),
            "health_category": hcat,
            "final_score": round(final, 2),
            "calories": r.nutrition.unit_serving_energy_kcal or r.nutrition.energy_kcal or 0.0,
            "protein_g": r.nutrition.unit_serving_protein_g or r.nutrition.protein_g or 0.0,
            "carbs_g": r.nutrition.unit_serving_carb_g or r.nutrition.carb_g or 0.0,
            "fat_g": r.nutrition.unit_serving_fat_g or r.nutrition.fat_g or 0.0,
            "fibre_g": r.nutrition.fibre_g or 0.0,
            "sugar_g": r.nutrition.freesugar_g or 0.0,
            "ingredient_match": {
                "score": round(match_score, 2),
                "matched": matched,
                "missing": missing[:5],  # show at most 5 missing
            },
            "reason": explanation["summary"],
        })

    return {
        "query": req,
        "total_results": len(candidate_scores),
        "top_recipes": top,
    }


@api.post("/recipes/filter", response_model=List[schemas_recipes.RecipeDetailResponse])
def filter_recipes(req: schemas_recipes.RecipeFilterRequest, db: Session = Depends(get_db)):
    """POST /recipes/filter — Filter recipes by nutrition, diet, cuisine, etc."""
    from sqlalchemy.orm import joinedload

    query = db.query(models.Recipe).options(
        joinedload(models.Recipe.nutrition),
        joinedload(models.Recipe.ingredients),
    )

    # Filters
    if req.category:
        query = query.filter(models.Recipe.category == req.category)
    if req.cuisine:
        query = query.filter(models.Recipe.cuisine.ilike(f"%{req.cuisine}%"))
    if req.difficulty:
        query = query.filter(models.Recipe.difficulty == req.difficulty)

    recipes = query.limit(req.max_results).all()

    # Apply post-filters that need nutrition data
    results = []
    for r in recipes:
        if r.nutrition:
            if req.min_protein is not None and (r.nutrition.protein_g or 0) < req.min_protein:
                continue
            if req.max_calories is not None and (r.nutrition.energy_kcal or 0) > req.max_calories:
                continue

        if req.max_cooking_time is not None:
            if req.max_cooking_time == 999 or req.max_cooking_time == 9999:
                if not r.cooking_time_minutes or r.cooking_time_minutes <= 60:
                    continue
            elif req.max_cooking_time > 0:
                if r.cooking_time_minutes and r.cooking_time_minutes > req.max_cooking_time:
                    continue

        # Diet type filter
        if req.diet_type:
            dt = req.diet_type.lower()
            if dt == "vegetarian" and not RecommendationEngine.is_vegetarian(r):
                continue
            if dt == "vegan" and not RecommendationEngine.is_vegan(r):
                continue

        # Goal filter: customize response
        hs, hcat, _ = HealthScorer.score_from_per_serving(r.nutrition) if r.nutrition else (50.0, "Moderate", "")

        ingredients_list = []
        for ing in r.ingredients:
            ingredients_list.append({
                "ingredient_name": ing.ingredient_name,
                "food_name": ing.food_name,
                "amount": ing.amount,
                "unit": ing.unit,
            })

        nutrition_data = None
        if r.nutrition:
            nutrition_data = {
                "energy_kcal": r.nutrition.energy_kcal,
                "unit_serving_energy_kcal": r.nutrition.unit_serving_energy_kcal,
                "protein_g": r.nutrition.protein_g,
                "carb_g": r.nutrition.carb_g,
                "fat_g": r.nutrition.fat_g,
                "freesugar_g": r.nutrition.freesugar_g,
                "fibre_g": r.nutrition.fibre_g,
                "sodium_mg": r.nutrition.sodium_mg,
            }

        desc = ""
        if r.instructions:
            first_sentence = r.instructions.split(".")[0].strip()
            if len(first_sentence) > 15:
                desc = first_sentence + "."
        if not desc or len(desc) < 15:
            ing_highlights = [i["food_name"] or i["ingredient_name"] for i in ingredients_list if i.get("food_name") or i.get("ingredient_name")][:3]
            ing_str = f" featuring {', '.join(ing_highlights)}" if ing_highlights else ""
            cal_val = nutrition_data.get('energy_kcal') if nutrition_data else 0
            cal_str = f" delivering ~{int(cal_val)} kcal" if cal_val else ""
            desc = f"A wholesome {r.cuisine or ''} {r.category or 'culinary specialty'}{ing_str}{cal_str} with balanced macro profile."

        results.append({
            "recipe_code": r.recipe_code,
            "recipe_name": r.recipe_name,
            "category": r.category,
            "cuisine": r.cuisine,
            "difficulty": r.difficulty,
            "cooking_time_minutes": r.cooking_time_minutes,
            "description": desc,
            "instructions": r.instructions,
            "primarysource": r.primarysource,
            "ingredients": ingredients_list,
            "nutrition": nutrition_data,
            "health_score": hs,
            "health_category": hcat,
        })

    return results


# =====================================================================
# EXISTING ENDPOINTS FOLLOW
# =====================================================================


@api.post("/track-weight")
def track_weight(req: schemas.TrackWeightRequest, db: Session = Depends(get_db)):
    """Log weight, dynamically update user profile metrics and water target, update adherence, and run adaptive planner."""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"User with ID {req.user_id} not found."
        )

    logged_at = req.logged_at or clock.today()

    # 1. Log weight
    # Delete existing log for same day if any, to update
    db.query(models.WeightLog).filter(
        models.WeightLog.user_id == req.user_id,
        models.WeightLog.logged_at == logged_at
    ).delete()

    db_log = models.WeightLog(
        user_id=req.user_id,
        weight=req.weight,
        logged_at=logged_at
    )
    db.add(db_log)

    # Update current user weight
    user.weight = req.weight

    # Dynamically update targets & water target with new weight
    targets = NutritionEngine.calculate_targets(
        age=user.age or 25,
        gender=user.gender or "male",
        height=user.height or 170.0,
        weight=req.weight,
        activity_level=user.activity_level or "sedentary",
        goal=user.goal or "maintenance"
    )
    user.target_calories = targets["target_calories"]
    user.target_protein = targets["target_protein_g"]
    user.target_carbs = targets["target_carbs_g"]
    user.target_fat = targets["target_fat_g"]
    user.water_target_ml = targets["water_target_ml"]

    # 2. Update adherence on meal plan for the day if specified
    if req.adherence is not None:
        meal_plan = db.query(models.GeneratedMealPlan).filter(
            models.GeneratedMealPlan.user_id == req.user_id,
            models.GeneratedMealPlan.plan_date == logged_at
        ).first()
        if meal_plan:
            meal_plan.adherence = req.adherence
        else:
            db_plan = models.GeneratedMealPlan(
                user_id=req.user_id,
                plan_date=logged_at,
                adherence=req.adherence
            )
            db.add(db_plan)

    db.commit()
    db.refresh(user)

    # 3. Run Adaptive Planner to check trends and adjust targets
    analysis = AdaptivePlanner.track_and_adjust(db=db, user_id=req.user_id)
    
    return {
        "status": "success",
        "weight_logged": {
            "weight": req.weight,
            "date": logged_at
        },
        "adherence_logged": req.adherence,
        "adaptive_adjustment": analysis,
        "user_profile": format_user_profile(user)
    }

@api.delete("/api/weight-logs/{log_id}")
def delete_weight_log(log_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Delete a specific weight log entry and restore previous latest weight."""
    db_log = db.query(models.WeightLog).filter(models.WeightLog.id == log_id).first()
    if not db_log or db_log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weight log entry not found.")
    user_id = db_log.user_id
    db.delete(db_log)
    db.commit()

    # Update latest weight on user profile if needed
    latest = db.query(models.WeightLog).filter(models.WeightLog.user_id == user_id).order_by(models.WeightLog.logged_at.desc()).first()
    if latest:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            user.weight = latest.weight
            targets = NutritionEngine.calculate_targets(
                age=user.age or 25,
                gender=user.gender or "male",
                height=user.height or 170.0,
                weight=latest.weight,
                activity_level=user.activity_level or "sedentary",
                goal=user.goal or "maintenance"
            )
            user.target_calories = targets["target_calories"]
            user.target_protein = targets["target_protein_g"]
            user.target_carbs = targets["target_carbs_g"]
            user.target_fat = targets["target_fat_g"]
            user.water_target_ml = targets["water_target_ml"]
            db.commit()

    return {"status": "success", "message": f"Deleted weight log {log_id}"}


# =====================================================================
# WATER LOGGING ENDPOINTS
# =====================================================================

@api.post("/api/water-logs", response_model=schemas.WaterLogResponse, status_code=status.HTTP_201_CREATED)
def log_water_intake(req: schemas.WaterLogCreate, db: Session = Depends(get_db)):
    """Log water intake for a user."""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {req.user_id} not found.")

    from datetime import datetime, date, time
    from sqlalchemy import or_, and_, func

    logged_date = req.logged_at or clock.today()

    db_log = models.WaterLog(
        user_id=req.user_id,
        amount_ml=req.amount_ml,
        logged_at=logged_date
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


@api.get("/api/water-logs/today/{user_id}", response_model=schemas.WaterTodayResponse)
def get_today_water_logs(user_id: int, log_date: Optional[str] = None, db: Session = Depends(get_db)):
    """Fetch all water logs for today (or specified date), along with total intake and personalized target."""
    from datetime import datetime, date, time
    from sqlalchemy import or_, and_, func
    try:
        target_date = date.fromisoformat(log_date) if log_date else clock.today()
    except Exception:
        target_date = clock.today()

    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    target_ml = 2500.0
    if user:
        target_ml = user.water_target_ml or NutritionEngine.calculate_water_target(user.weight or 70.0, user.activity_level or "sedentary")

    logs = db.query(models.WaterLog).filter(
        models.WaterLog.user_id == user_id,
        or_(
            models.WaterLog.logged_at == target_date,
            and_(models.WaterLog.logged_at >= start_of_day, models.WaterLog.logged_at <= end_of_day),
            func.date(models.WaterLog.logged_at) == target_date.isoformat()
        )
    ).order_by(models.WaterLog.id.asc()).all()

    total_ml = sum(float(l.amount_ml or 0.0) for l in logs)
    pct = round((total_ml / target_ml * 100.0), 1) if target_ml > 0 else 0.0

    return {
        "user_id": user_id,
        "date": target_date,
        "total_ml": round(total_ml, 1),
        "target_ml": round(target_ml, 1),
        "progress_pct": min(pct, 200.0),
        "logs": logs
    }


@api.get("/api/water-logs/history/{user_id}", response_model=schemas.WaterHistoryResponse)
def get_water_history(user_id: int, days: int = 30, db: Session = Depends(get_db)):
    """Fetch daily aggregated water intake history for trends."""
    from datetime import date, timedelta
    from sqlalchemy import func
    cutoff = clock.today() - timedelta(days=days)
    records = db.query(
        models.WaterLog.logged_at,
        func.sum(models.WaterLog.amount_ml).label("total_ml")
    ).filter(
        models.WaterLog.user_id == user_id,
        models.WaterLog.logged_at >= cutoff
    ).group_by(models.WaterLog.logged_at).order_by(models.WaterLog.logged_at.asc()).all()

    history = [
        {"date": r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]), "total_ml": round(float(r[1] or 0.0), 1)}
        for r in records
    ]
    return {"user_id": user_id, "history": history}


@api.delete("/api/water-logs/{log_id}")
def delete_water_log(log_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Delete a specific water log entry."""
    db_log = db.query(models.WaterLog).filter(models.WaterLog.id == log_id).first()
    if not db_log or db_log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Water log entry not found.")
    db.delete(db_log)
    db.commit()
    return {"status": "success", "message": f"Deleted water log {log_id}"}


# =====================================================================
# NEW CORE ENGINE ENDPOINTS (PHASE 2 & 3)
# =====================================================================

@api.post("/api/classify", response_model=schemas.ClassifyResponse)
def classify_food(req: schemas.ClassifyRequest, db: Session = Depends(get_db)):
    """Classify ingredients list or an existing recipe against dietary rules (Vegetarian, Vegan, Jain, Eggetarian, Keto, Paleo, etc.)."""
    if req.recipe_code:
        recipe = db.query(models.Recipe).filter(models.Recipe.recipe_code == req.recipe_code).first()
        if not recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recipe '{req.recipe_code}' not found."
            )
        classification = ClassificationEngine.classify_recipe(db, recipe)
    elif req.ingredients:
        rules_map = ClassificationEngine.get_rules_map(db)
        classification = ClassificationEngine.classify_ingredients(req.ingredients, rules_map)
        classification["tags"] = []
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either recipe_code or ingredients list."
        )
    return classification


@api.post("/api/classify/substitutions", response_model=schemas.SubstitutionResponse)
def get_dietary_substitutions(req: schemas.SubstitutionRequest):
    """Retrieve intelligent culinary authentic substitutions for non-compliant ingredients under a target diet."""
    if not req.ingredients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a non-empty list of ingredients."
        )
    subs = ClassificationEngine.get_substitutions(req.ingredients, req.target_diet)
    return {
        "target_diet": req.target_diet,
        "substitutions": subs
    }



@api.get("/api/barcode/{barcode}")
def scan_barcode(barcode: str, diet_type: Optional[str] = None, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Fetch product details by barcode, utilizing local caching, Open Food Facts API, web scraper, and Gemini API."""
    if user_id and not diet_type:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            diet_type = user.diet_type
    result = BarcodeService.get_product(db, barcode, diet_type=diet_type or "all")
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    return result


@api.post("/api/barcode/scan-image")
async def scan_barcode_from_image(
    file: UploadFile = File(...),
    diet_type: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Detect barcode and/or OCR nutrition facts from uploaded image using OpenCV/Gemini Vision AI."""
    user_id = current_user.id  # never trust a client-supplied id
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image file uploaded.")

    if user_id and not diet_type:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            diet_type = user.diet_type

    # 1. Try to detect barcode number
    barcode = BarcodeService.detect_barcode_from_image(contents)
    product = None
    if barcode:
        product = BarcodeService.get_product(db, barcode, diet_type=diet_type or "all")

    # 2. Extract OCR label facts
    ocr_result = OCREngine.parse_label_image(contents)
    has_valid_ocr = bool(ocr_result and (
        (ocr_result.get("nutrients") and float(ocr_result["nutrients"].get("energy_kcal", 0.0) or 0.0) > 0.0) or
        (ocr_result.get("detected_text") and len(ocr_result["detected_text"].strip()) > 10)
    ))

    # 3. Return appropriate response
    if barcode and product and product.get("status") == "success":
        if has_valid_ocr:
            return {
                "type": "dual",
                "barcode": barcode,
                "product": product,
                "ocr_result": ocr_result
            }
        return {
            "type": "barcode",
            "barcode": barcode,
            "product": product
        }

    if has_valid_ocr:
        return {
            "type": "ocr",
            "ocr_result": ocr_result
        }

    raise HTTPException(
        status_code=400,
        detail="Could not detect a clear barcode or nutrition facts label in the image. Please try a clearer photo or enter the barcode manually."
    )


@api.post("/api/barcode/manual")
def save_manual_barcode(req: schemas.ManualBarcodeRequest, db: Session = Depends(get_db)):
    """Manually add barcode details and save to cache."""
    import json
    
    # Check if barcode already exists
    existing = db.query(models.BarcodeCache).filter(models.BarcodeCache.barcode == req.barcode).first()
    if existing:
        db.delete(existing)
        db.commit()

    nutrients_100g = {
        "energy_kcal": req.energy_kcal,
        "protein_g": req.protein_g,
        "carb_g": req.carb_g,
        "fat_g": req.fat_g,
        "fibre_g": req.fibre_g,
        "sodium_mg": req.sodium_mg,
        "sugar_g": req.sugar_g,
        "saturated_fat_g": req.saturated_fat_g
    }

    # Calculate local health score
    score, category, explanation = HealthScorer.score_from_nutrition_dict(nutrients_100g)

    new_cache = models.BarcodeCache(
        barcode=req.barcode,
        product_name=req.product_name,
        brand=req.brand,
        ingredients_text=req.ingredients_text,
        nutrition_grade=category[0].lower() if (category and len(category) > 0) else "unknown",
        nutriments_json=json.dumps(nutrients_100g),
        health_score=score,
        health_category=category
    )
    db.add(new_cache)
    db.commit()
    db.refresh(new_cache)

    return {
        "status": "success",
        "source": "manual",
        "barcode": req.barcode,
        "product_name": req.product_name,
        "brand": req.brand,
        "ingredients_text": req.ingredients_text,
        "nutrition_grade": new_cache.nutrition_grade,
        "health_score": score,
        "health_category": category,
        "explanation": explanation,
        "nutriments": nutrients_100g
    }


ALTERNATIVES_LIST = [
    {
        "keywords": ["chips", "kurkure", "lays", "bingo", "fried", "namkeen", "crisps", "snack"],
        "category": "Snack",
        "name": "Tata Sampann Roasted Chana (Spiced)",
        "price": 30,
        "protein_g": 20.0,
        "energy_kcal": 360,
        "link": "https://www.amazon.in/dp/B09D3R5WYS",
        "reason": "100% roasted, high-protein snack (20g protein per 100g), low fat, and extremely budget-friendly!"
    },
    {
        "keywords": ["coke", "cola", "pepsi", "sprite", "fanta", "maaza", "frooti", "soda", "drink", "juice", "beverage", "nimbu"],
        "category": "Snack",
        "name": "Amul Masti Spiced Buttermilk (Chaas)",
        "price": 15,
        "protein_g": 1.5,
        "energy_kcal": 28,
        "link": "https://www.amazon.in/dp/B084G2W3R8",
        "reason": "Refreshing, low calorie (only 28 kcal), completely sugar-free natural probiotic drink for the same cost as soda!"
    },
    {
        "keywords": ["biscuit", "parle", "marie", "cookies", "good day", "cracker"],
        "category": "Snack",
        "name": "Yoga Bar Oats (Instant)",
        "price": 45,
        "protein_g": 13.6,
        "energy_kcal": 390,
        "link": "https://www.amazon.in/dp/B08PBDZYZK",
        "reason": "100% whole grain oats, high fibre, low glycemic index, and significantly higher protein than refined flour biscuits."
    },
    {
        "keywords": ["chips", "kurkure", "lays", "bingo", "fried", "namkeen", "crisps", "snack"],
        "category": "Snack",
        "name": "Happilo Premium Roasted Makhana (Salt & Pepper)",
        "price": 120,
        "protein_g": 9.0,
        "energy_kcal": 350,
        "link": "https://www.amazon.in/dp/B07NPHSP8N",
        "reason": "Baked and roasted instead of deep fried, lower in saturated fats and contains 9g protein!"
    },
    {
        "keywords": ["coke", "cola", "pepsi", "sprite", "fanta", "maaza", "frooti", "soda", "drink", "juice", "beverage", "nimbu"],
        "category": "Snack",
        "name": "Paper Boat Tender Coconut Water",
        "price": 40,
        "protein_g": 0.0,
        "energy_kcal": 20,
        "link": "https://www.amazon.in/dp/B01H7B7T58",
        "reason": "100% natural, no added white sugar, high in potassium and hydration compared to sugary sodas."
    },
    {
        "keywords": ["bar", "chocolate", "cadbury", "dairymilk", "snickers", "kitkat", "candy", "sweet", "protein bar"],
        "category": "Snack",
        "name": "The Whole Truth Protein Bars (Double Cocoa)",
        "price": 100,
        "protein_g": 25.0,
        "energy_kcal": 366,
        "link": "https://www.amazon.in/dp/B08L84Q1V2",
        "reason": "Clean ingredients (only dates, whey protein, cocoa, almonds), no added sugar, and gives 15g protein per bar!"
    },
    {
        "keywords": ["yogabar", "protein bar", "muesli bar", "granola bar"],
        "category": "Snack",
        "name": "MuscleBlaze Protein Bar (Choco Delight)",
        "price": 90,
        "protein_g": 22.0,
        "energy_kcal": 380,
        "link": "https://www.amazon.in/dp/B07K48C9M4",
        "reason": "Higher protein content (22g protein vs 10g in standard bars) for the same price point."
    },
    {
        "keywords": ["noodles", "maggi", "yippee", "ramen", "pasta"],
        "category": "Lunch/Dinner",
        "name": "Slurrp Farm Millet Noodles",
        "price": 80,
        "protein_g": 12.0,
        "energy_kcal": 360,
        "link": "https://www.amazon.in/dp/B08P8LFSQ7",
        "reason": "Made from foxtail millet and wheat, not maida, and provides 12g protein per 100g."
    },
    {
        "keywords": ["biscuit", "parle", "marie", "cookies", "good day", "cracker"],
        "category": "Snack",
        "name": "NutroActive Keto Cookies (High Protein & Low Carb)",
        "price": 150,
        "protein_g": 20.0,
        "energy_kcal": 450,
        "link": "https://www.amazon.in/dp/B07GD4Z8K3",
        "reason": "Low glycemic load, only 3g net carbs per cookie and extremely high protein (20g per 100g)."
    }
]


@api.post("/api/barcode/alternatives")
def get_barcode_alternatives(req: schemas.AlternativesRequest):
    """Recommend healthier alternative products based on meal type, nutrients, and price range."""
    name_lower = req.product_name.lower()
    
    # 1. Try keyword matching on alternative database
    matched_alts = []
    for alt in ALTERNATIVES_LIST:
        if any(kw in name_lower for kw in alt["keywords"]):
            matched_alts.append(alt)
            
    # 2. Fallback to category/macro matching if no keywords match
    if not matched_alts:
        if req.sugar_g > 10.0 or req.energy_kcal > 250:
            matched_alts.append(ALTERNATIVES_LIST[0]) # Chana
            matched_alts.append(ALTERNATIVES_LIST[1]) # Chaas
            matched_alts.append(ALTERNATIVES_LIST[5]) # Whole Truth Bar
        else:
            if req.meal_type == "Snack":
                matched_alts.append(ALTERNATIVES_LIST[0])
                matched_alts.append(ALTERNATIVES_LIST[1])
            else:
                matched_alts.append(ALTERNATIVES_LIST[7]) # Millet Noodles

    results = []
    for alt in matched_alts:
        # Distance calculation for budget matching
        price_diff = abs(alt["price"] - req.estimated_price)
        
        # Heavy penalty on premium products if scanned product was budget (<= 40 INR)
        penalty = 0.0
        if req.estimated_price <= 40.0 and alt["price"] > 70.0:
            penalty = 200.0  # pushes them down the rank
            
        protein_diff = alt["protein_g"] - req.protein_g
        kcal_diff = req.energy_kcal - alt["energy_kcal"]
        
        comparison = ""
        if protein_diff > 0:
            comparison += f"Provides {protein_diff:.1f}g MORE protein per 100g. "
        if kcal_diff > 0:
            comparison += f"Saves {kcal_diff:.0f} kcal per 100g. "
            
        results.append({
            "name": alt["name"],
            "price": alt["price"],
            "protein_g": alt["protein_g"],
            "energy_kcal": alt["energy_kcal"],
            "link": alt["link"],
            "reason": alt["reason"],
            "comparison": comparison or "Higher nutritional density.",
            "rank_score": price_diff + penalty
        })
        
    # Sort results by price/budget rank score
    results.sort(key=lambda x: x["rank_score"])
    
    # Remove rank_score from final response to keep clean contract
    for r in results:
        r.pop("rank_score", None)
        
    return {"alternatives": results}


from fastapi import UploadFile, File, Form

@api.post("/api/ocr")
def ocr_image(
    file: UploadFile = File(...),
    user_id: Optional[int] = Form(None),
    meal_type: Optional[str] = Form(None),
    food_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Process an uploaded nutrition label image to extract nutritional values."""
    user_id = current_user.id  # never trust a client-supplied id
    contents = file.file.read()
    res = OCREngine.extract_nutrition_from_image(contents)
    
    # Save metadata/log if user info is provided
    if user_id and meal_type and res["status"] == "success":
        parsed = res["parsed_nutrition"]
        food_label = food_name or file.filename or "Scanned Label"
        db_log = models.MealLog(
            user_id=user_id,
            log_date=clock.today(),
            meal_type=meal_type,
            food_name=food_label,
            calories=parsed["energy_kcal"],
            protein=parsed["protein_g"],
            carbs=parsed["carb_g"],
            fat=parsed["fat_g"],
            source="ocr_label"
        )
        db.add(db_log)
        db.commit()
        sync_daily_macros(db, user_id, db_log.log_date)
        res["meal_logged"] = True
        
    return res


@api.get("/api/analytics/{user_id}")
def get_user_analytics(user_id: int, db: Session = Depends(get_db)):
    """Retrieve nutritional statistics and weight trend analysis for the user."""
    result = AnalyticsEngine.calculate_and_save_metrics(db, user_id)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["message"]
        )
    return result


@api.get("/api/analytics/{user_id}/history")
def get_user_analytics_history(
    user_id: int,
    metric_name: str,
    limit: int = 30,
    db: Session = Depends(get_db)
):
    """Retrieve historical values of a specific calculated analytics metric."""
    return AnalyticsEngine.get_historical_metrics(db, user_id, metric_name, limit)


def format_homely_meal_response(m):
    return {
        "id": m.id,
        "name": m.name,
        "creator_id": m.creator_id,
        "is_community": m.is_community,
        "status": m.status,
        "popularity": m.popularity,
        "cuisine": m.cuisine,
        "region": m.region,
        "created_at": m.created_at,
        "ingredients": [
            {
                "ingredient_name": ing.ingredient_name,
                "amount": ing.amount,
                "unit": ing.unit,
                "gram_weight": ing.gram_weight,
                "food_code": ing.food_code
            } for ing in m.ingredients
        ],
        "nutrition": {
            "energy_kcal": m.nutrition.energy_kcal if m.nutrition else 0.0,
            "protein_g": m.nutrition.protein_g if m.nutrition else 0.0,
            "carb_g": m.nutrition.carb_g if m.nutrition else 0.0,
            "fat_g": m.nutrition.fat_g if m.nutrition else 0.0,
            "fibre_g": m.nutrition.fibre_g if m.nutrition else 0.0,
            "sodium_mg": m.nutrition.sodium_mg if m.nutrition else 0.0,
            "sugar_g": m.nutrition.sugar_g if m.nutrition else 0.0
        } if m.nutrition else None,
        "tags": [t.tag for t in m.tags]
    }


@api.get("/api/homely/builder-defaults")
def get_homely_builder_defaults(db: Session = Depends(get_db)):
    """Get defaults for homely meal builder including base items and condiments."""
    from sqlalchemy.orm import joinedload
    
    # We query the food items from database
    codes = {
        "paneer_tikka": "IND_FOOD_0078",
        "chicken_tikka": "IND_FOOD_0026",
        "mint_chutney": "IND_FOOD_0045",
        "tamarind_chutney": "IND_FOOD_0046",
        "tomato_sauce": "PACKAGED_0756",
        "curd": "PACKAGED_0902"
    }
    
    # Fetch them
    items = db.query(models.Food).options(joinedload(models.Food.nutrients)).filter(models.Food.food_code.in_(list(codes.values()))).all()
    items_map = {item.food_code: item for item in items}
    
    def get_nutrients_or_fallback(code, fallback_dict):
        item = items_map.get(code)
        if item and item.nutrients and (item.nutrients.energy_kcal or 0) > 0:
            n = item.nutrients
            return {
                "name": item.name,
                "energy_kcal": n.energy_kcal,
                "protein_g": n.protein_g,
                "carb_g": n.carb_g,
                "fat_g": n.fat_g,
                "fibre_g": n.fibre_g or 0.0,
                "sodium_mg": n.sodium_mg or 0.0,
                "sugar_g": n.sugar_g or 0.0
            }
        return fallback_dict

    base_meals = [
        {
            "code": "IND_FOOD_0078",
            "name": "Paneer Tikka (Home Made)",
            "unit": "piece",
            "unit_weight_g": 25.0,
            "type": "Standard",
            "nutrients_100g": get_nutrients_or_fallback("IND_FOOD_0078", {
                "name": "Paneer Tikka", "energy_kcal": 190.0, "protein_g": 14.0, "carb_g": 4.5, "fat_g": 13.0, "fibre_g": 0.5, "sodium_mg": 380.0, "sugar_g": 1.2
            })
        },
        {
            "code": "IND_FOOD_0026",
            "name": "Chicken Tikka (Home Made)",
            "unit": "piece",
            "unit_weight_g": 30.0,
            "type": "Standard",
            "nutrients_100g": get_nutrients_or_fallback("IND_FOOD_0026", {
                "name": "Chicken Tikka", "energy_kcal": 150.0, "protein_g": 18.0, "carb_g": 3.0, "fat_g": 7.0, "fibre_g": 0.2, "sodium_mg": 410.0, "sugar_g": 0.8
            })
        },
        {
            "code": "Roti",
            "name": "Wheat Roti / Chapati",
            "unit": "piece",
            "unit_weight_g": 35.0,
            "type": "Standard",
            "nutrients_100g": {
                "name": "Roti", "energy_kcal": 240.0, "protein_g": 8.0, "carb_g": 48.0, "fat_g": 2.0, "fibre_g": 6.5, "sodium_mg": 180.0, "sugar_g": 1.0
            }
        },
        {
            "code": "Dal_Tadka",
            "name": "Yellow Dal Tadka",
            "unit": "bowl",
            "unit_weight_g": 150.0,
            "type": "Standard",
            "nutrients_100g": {
                "name": "Dal Tadka", "energy_kcal": 115.0, "protein_g": 6.2, "carb_g": 16.0, "fat_g": 3.5, "fibre_g": 3.8, "sodium_mg": 320.0, "sugar_g": 0.8
            }
        },
        {
            "code": "Samosa",
            "name": "Samosa (Home Made)",
            "unit": "piece",
            "unit_weight_g": 50.0,
            "type": "Standard",
            "nutrients_100g": {
                "name": "Samosa", "energy_kcal": 260.0, "protein_g": 4.5, "carb_g": 32.0, "fat_g": 12.0, "fibre_g": 1.5, "sodium_mg": 290.0, "sugar_g": 1.0
            }
        },
        {
            "code": "Dhokla",
            "name": "Khaman Dhokla (Home Made)",
            "unit": "piece",
            "unit_weight_g": 35.0,
            "type": "Standard",
            "nutrients_100g": {
                "name": "Dhokla", "energy_kcal": 160.0, "protein_g": 6.0, "carb_g": 28.0, "fat_g": 2.5, "fibre_g": 1.8, "sodium_mg": 340.0, "sugar_g": 4.0
            }
        },
        {
            "code": "Idli",
            "name": "Idli (Home Made)",
            "unit": "piece",
            "unit_weight_g": 40.0,
            "type": "Standard",
            "nutrients_100g": {
                "name": "Idli", "energy_kcal": 100.0, "protein_g": 2.5, "carb_g": 22.0, "fat_g": 0.2, "fibre_g": 1.0, "sodium_mg": 120.0, "sugar_g": 0.2
            }
        },
        {
            "code": "Dosa",
            "name": "Plain Dosa (Home Made)",
            "unit": "serving",
            "unit_weight_g": 80.0,
            "type": "Standard",
            "nutrients_100g": {
                "name": "Dosa", "energy_kcal": 170.0, "protein_g": 4.0, "carb_g": 35.0, "fat_g": 1.5, "fibre_g": 1.2, "sodium_mg": 180.0, "sugar_g": 0.3
            }
        }
    ]

    # Query approved Community Homely Meals to include in base selections
    try:
        comm_meals = db.query(models.HomelyMeal).options(joinedload(models.HomelyMeal.nutrition)).filter(
            models.HomelyMeal.status == "approved"
        ).order_by(models.HomelyMeal.id.desc()).limit(20).all()
        for cm in comm_meals:
            nut = cm.nutrition
            if nut and nut.energy_kcal:
                base_meals.append({
                    "code": f"HOMELY_{cm.id}",
                    "name": f"{cm.name} (Community)",
                    "unit": "serving",
                    "unit_weight_g": 100.0,
                    "type": "Community",
                    "nutrients_100g": {
                        "name": cm.name,
                        "energy_kcal": float(nut.energy_kcal),
                        "protein_g": float(nut.protein_g or 0.0),
                        "carb_g": float(nut.carb_g or 0.0),
                        "fat_g": float(nut.fat_g or 0.0),
                        "fibre_g": float(getattr(nut, "fibre_g", 0.0) or 0.0),
                        "sodium_mg": float(getattr(nut, "sodium_mg", 0.0) or 0.0),
                        "sugar_g": float(getattr(nut, "sugar_g", 0.0) or 0.0)
                    }
                })
    except Exception as e:
        logger.warning(f"Error querying community meals for builder defaults: {e}")

    condiments = [
        {
            "id": "curd_raita",
            "name": "Dahi / Fresh Curd / Raita",
            "unit": "tbsp",
            "unit_weight_g": 20.0,
            "nutrients_100g": get_nutrients_or_fallback("PACKAGED_0902", {
                "name": "Dahi Curd", "energy_kcal": 60.0, "protein_g": 3.5, "carb_g": 4.7, "fat_g": 3.2, "fibre_g": 0.0, "sodium_mg": 50.0, "sugar_g": 4.0
            })
        },
        {
            "id": "green_chutney",
            "name": "Green Chutney (Mint & Coriander)",
            "unit": "tsp",
            "unit_weight_g": 5.0,
            "nutrients_100g": get_nutrients_or_fallback("IND_FOOD_0045", {
                "name": "Mint Chutney", "energy_kcal": 40.0, "protein_g": 2.0, "carb_g": 6.0, "fat_g": 1.0, "fibre_g": 2.0, "sodium_mg": 600.0, "sugar_g": 0.5
            })
        },
        {
            "id": "imli_chutney",
            "name": "Imli Chutney (Sweet Tamarind)",
            "unit": "tsp",
            "unit_weight_g": 5.0,
            "nutrients_100g": get_nutrients_or_fallback("IND_FOOD_0046", {
                "name": "Tamarind Chutney", "energy_kcal": 180.0, "protein_g": 1.0, "carb_g": 45.0, "fat_g": 0.2, "fibre_g": 1.5, "sodium_mg": 450.0, "sugar_g": 38.0
            })
        },
        {
            "id": "garlic_chutney",
            "name": "Red Garlic Chutney (Lahsun)",
            "unit": "tsp",
            "unit_weight_g": 5.0,
            "nutrients_100g": {
                "name": "Garlic Chutney", "energy_kcal": 125.0, "protein_g": 3.0, "carb_g": 12.0, "fat_g": 7.0, "fibre_g": 2.5, "sodium_mg": 680.0, "sugar_g": 1.5
            }
        },
        {
            "id": "coconut_chutney",
            "name": "Fresh Coconut Chutney",
            "unit": "tbsp",
            "unit_weight_g": 15.0,
            "nutrients_100g": {
                "name": "Coconut Chutney", "energy_kcal": 210.0, "protein_g": 3.2, "carb_g": 8.5, "fat_g": 18.0, "fibre_g": 4.0, "sodium_mg": 380.0, "sugar_g": 2.0
            }
        },
        {
            "id": "gunpowder_podi",
            "name": "Gunpowder / Idli Podi + Oil",
            "unit": "tsp",
            "unit_weight_g": 5.0,
            "nutrients_100g": {
                "name": "Gunpowder Podi", "energy_kcal": 360.0, "protein_g": 15.0, "carb_g": 30.0, "fat_g": 20.0, "fibre_g": 8.0, "sodium_mg": 550.0, "sugar_g": 1.0
            }
        },
        {
            "id": "tomato_sauce",
            "name": "Tomato Ketchup / Sauce",
            "unit": "tsp",
            "unit_weight_g": 5.0,
            "nutrients_100g": get_nutrients_or_fallback("PACKAGED_0756", {
                "name": "Tomato Sauce", "energy_kcal": 120.0, "protein_g": 1.0, "carb_g": 29.0, "fat_g": 0.1, "fibre_g": 0.8, "sodium_mg": 900.0, "sugar_g": 22.0
            })
        },
        {
            "id": "butter_ghee",
            "name": "Desi Ghee / Butter",
            "unit": "tsp",
            "unit_weight_g": 5.0,
            "nutrients_100g": {
                "name": "Butter", "energy_kcal": 717.0, "protein_g": 0.8, "carb_g": 0.1, "fat_g": 81.0, "fibre_g": 0.0, "sodium_mg": 643.0, "sugar_g": 0.1
            }
        },
        {
            "id": "crispy_sev",
            "name": "Crispy Sev / Bhujia Topping",
            "unit": "tbsp",
            "unit_weight_g": 10.0,
            "nutrients_100g": {
                "name": "Sev Bhujia", "energy_kcal": 560.0, "protein_g": 12.0, "carb_g": 42.0, "fat_g": 38.0, "fibre_g": 4.5, "sodium_mg": 720.0, "sugar_g": 1.5
            }
        },
        {
            "id": "roasted_peanuts",
            "name": "Roasted Peanuts / Seeds",
            "unit": "tbsp",
            "unit_weight_g": 10.0,
            "nutrients_100g": {
                "name": "Peanuts", "energy_kcal": 567.0, "protein_g": 25.8, "carb_g": 16.1, "fat_g": 49.2, "fibre_g": 8.5, "sodium_mg": 18.0, "sugar_g": 4.7
            }
        },
        {
            "id": "grated_paneer",
            "name": "Grated Fresh Paneer",
            "unit": "tbsp",
            "unit_weight_g": 15.0,
            "nutrients_100g": {
                "name": "Paneer", "energy_kcal": 265.0, "protein_g": 18.3, "carb_g": 3.4, "fat_g": 20.8, "fibre_g": 0.0, "sodium_mg": 22.0, "sugar_g": 1.5
            }
        },
        {
            "id": "shredded_cheese",
            "name": "Shredded Processed Cheese",
            "unit": "tbsp",
            "unit_weight_g": 15.0,
            "nutrients_100g": {
                "name": "Cheese", "energy_kcal": 320.0, "protein_g": 20.0, "carb_g": 2.5, "fat_g": 26.0, "fibre_g": 0.0, "sodium_mg": 850.0, "sugar_g": 0.5
            }
        },
        {
            "id": "spicy_pickle",
            "name": "Mango / Lime Pickle (Achar)",
            "unit": "tsp",
            "unit_weight_g": 5.0,
            "nutrients_100g": {
                "name": "Pickle", "energy_kcal": 175.0, "protein_g": 2.0, "carb_g": 11.0, "fat_g": 14.0, "fibre_g": 3.0, "sodium_mg": 1200.0, "sugar_g": 2.0
            }
        },
        {
            "id": "fried_onions",
            "name": "Fried Onions (Birista)",
            "unit": "tbsp",
            "unit_weight_g": 10.0,
            "nutrients_100g": {
                "name": "Fried Onions", "energy_kcal": 490.0, "protein_g": 4.5, "carb_g": 48.0, "fat_g": 32.0, "fibre_g": 6.0, "sodium_mg": 280.0, "sugar_g": 8.0
            }
        },
        {
            "id": "lemon_juice_masala",
            "name": "Fresh Lemon Juice & Chaat Masala",
            "unit": "tsp",
            "unit_weight_g": 5.0,
            "nutrients_100g": {
                "name": "Lemon Chaat", "energy_kcal": 25.0, "protein_g": 0.4, "carb_g": 6.0, "fat_g": 0.2, "fibre_g": 0.3, "sodium_mg": 480.0, "sugar_g": 1.5
            }
        }
    ]

    return {"base_meals": base_meals, "condiments": condiments}


@api.post("/api/homely-meals/calculate", response_model=schemas.HomelyMealCalculateResponse)
def calculate_homely_meal(req: schemas.HomelyMealCalculateRequest, db: Session = Depends(get_db)):
    """Computes nutrition parameters of raw ingredients list on-the-fly."""
    res = homely_meals_engine.calculate_meal_nutrition(db, req.ingredients)
    return res

@api.post("/api/homely-meals/create", response_model=schemas.HomelyMealResponse)
def create_custom_homely_meal(req: schemas.HomelyMealCreateRequest, db: Session = Depends(get_db)):
    """Adds a homely meal to the database (defaults to status='pending')."""
    meal = homely_meals_engine.create_homely_meal(db, req)
    return format_homely_meal_response(meal)

@api.get("/api/homely-meals/user/{user_id}", response_model=List[schemas.HomelyMealResponse])
def get_user_homely_meals(user_id: int, db: Session = Depends(get_db)):
    """Retrieve all homely meals created by a specific user."""
    from sqlalchemy.orm import joinedload
    meals = db.query(models.HomelyMeal).options(
        joinedload(models.HomelyMeal.nutrition),
        joinedload(models.HomelyMeal.ingredients),
        joinedload(models.HomelyMeal.tags)
    ).filter(models.HomelyMeal.creator_id == user_id).order_by(models.HomelyMeal.created_at.desc()).all()
    return [format_homely_meal_response(m) for m in meals]

@api.get("/api/homely-meals/pending", response_model=List[schemas.HomelyMealResponse])
def get_pending_homely_meals(exclude_creator_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Retrieve all pending homely meals for community kitchen moderation."""
    from sqlalchemy.orm import joinedload
    query = db.query(models.HomelyMeal).options(
        joinedload(models.HomelyMeal.nutrition),
        joinedload(models.HomelyMeal.ingredients),
        joinedload(models.HomelyMeal.tags)
    ).filter(models.HomelyMeal.status == "pending")
    if exclude_creator_id:
        query = query.filter(models.HomelyMeal.creator_id != exclude_creator_id)
    meals = query.all()
    return [format_homely_meal_response(m) for m in meals]

@api.post("/api/homely-meals/review/{meal_id}", response_model=schemas.HomelyMealResponse)
def review_homely_meal(meal_id: int, req: schemas.HomelyMealStatusUpdateRequest, db: Session = Depends(get_db)):
    """Approves or rejects a user-submitted meal for community use."""
    meal = homely_meals_engine.update_meal_status(db, meal_id, req.status, req.reviewer_id, req.comment)
    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Homely meal with ID {meal_id} not found."
        )
    return format_homely_meal_response(meal)

@api.get("/api/homely-meals/search", response_model=List[schemas.HomelyMealResponse])
def search_homely_meals(q: str = "", db: Session = Depends(get_db)):
    """Fuzzy searches approved community homely meals."""
    from sqlalchemy.orm import joinedload
    query = db.query(models.HomelyMeal).options(
        joinedload(models.HomelyMeal.nutrition),
        joinedload(models.HomelyMeal.ingredients),
        joinedload(models.HomelyMeal.tags)
    ).filter(models.HomelyMeal.status == "approved")
    
    if q.strip():
        query = query.filter(models.HomelyMeal.name.ilike(f"%{q}%"))
        
    meals = query.all()
    return [format_homely_meal_response(m) for m in meals]

@api.get("/api/homely-meals/{meal_id}", response_model=schemas.HomelyMealResponse)
def get_homely_meal_detail(meal_id: int, scale: float = 1.0, db: Session = Depends(get_db)):
    """Retrieves meal components and allows custom quantity scaling."""
    from sqlalchemy.orm import joinedload
    meal = db.query(models.HomelyMeal).options(
        joinedload(models.HomelyMeal.nutrition),
        joinedload(models.HomelyMeal.ingredients),
        joinedload(models.HomelyMeal.tags)
    ).filter(models.HomelyMeal.id == meal_id).first()
    
    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Homely meal with ID {meal_id} not found."
        )
        
    res = format_homely_meal_response(meal)
    
    if scale != 1.0:
        for ing in res["ingredients"]:
            ing["amount"] = round(ing["amount"] * scale, 2)
            ing["gram_weight"] = round(ing["gram_weight"] * scale, 2)
        if res["nutrition"]:
            for k in res["nutrition"]:
                res["nutrition"][k] = round(res["nutrition"][k] * scale, 2)
                
    return res

@api.post("/api/homely-meals/{meal_id}/review", response_model=schemas.HomelyMealReviewResponse)
def review_comment_homely_meal(meal_id: int, req: schemas.HomelyMealReviewRequest, db: Session = Depends(get_db)):
    """Submit rating and comment for a homely meal."""
    meal = db.query(models.HomelyMeal).filter(models.HomelyMeal.id == meal_id).first()
    if not meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Homely meal with ID {meal_id} not found."
        )
    review = homely_meals_engine.add_review(db, meal_id, req.reviewer_id, req.rating, req.comment)
    return review

@api.post("/api/meal-logs", response_model=schemas.MealLogResponse, status_code=status.HTTP_201_CREATED)
def log_meal_directly(req: schemas.MealLogCreate, db: Session = Depends(get_db)):
    """Log a meal intake for tracking metrics."""
    target_date = req.log_date
    if isinstance(target_date, str):
        try:
            target_date = date.fromisoformat(target_date)
        except Exception:
            target_date = clock.today()
    elif not target_date:
        target_date = clock.today()

    db_log = models.MealLog(
        user_id=req.user_id,
        log_date=target_date,
        meal_type=req.meal_type or "Snack",
        food_name=req.food_name,
        calories=float(req.calories or 0.0),
        protein=float(req.protein or 0.0),
        carbs=float(req.carbs or 0.0),
        fat=float(req.fat or 0.0),
        weight_g=req.weight_g,
        source=req.source or "manual",
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    sync_daily_macros(db, db_log.user_id, db_log.log_date)
    return db_log


@api.get("/api/meal-logs/today/{user_id}")
def get_today_meal_logs(user_id: int, log_date: Optional[str] = None, db: Session = Depends(get_db)):
    """Fetch all meal logs for the given user for today (or specified date) with macro totals and targets comparison."""
    from datetime import date
    try:
        target_date = date.fromisoformat(log_date) if log_date else clock.today()
    except Exception:
        target_date = clock.today()

    logs = db.query(models.MealLog).filter(
        models.MealLog.user_id == user_id,
        models.MealLog.log_date == target_date
    ).order_by(models.MealLog.id.asc()).all()
    
    total_cal = sum(float(l.calories or 0.0) for l in logs)
    total_p = sum(float(l.protein or 0.0) for l in logs)
    total_c = sum(float(l.carbs or 0.0) for l in logs)
    total_f = sum(float(l.fat or 0.0) for l in logs)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    target_cal = float(user.target_calories or 2000.0) if user else 2000.0
    target_p = float(user.target_protein or 140.0) if user else 140.0
    target_c = float(user.target_carbs or 220.0) if user else 220.0
    target_f = float(user.target_fat or 60.0) if user else 60.0
    
    return {
        "user_id": user_id,
        "date": target_date.isoformat(),
        "totals": {
            "calories": round(total_cal, 1),
            "protein": round(total_p, 1),
            "carbs": round(total_c, 1),
            "fat": round(total_f, 1)
        },
        "targets": {
            "calories": round(target_cal, 1),
            "protein": round(target_p, 1),
            "carbs": round(target_c, 1),
            "fat": round(target_f, 1)
        },
        "logs": [
            {
                "id": l.id,
                "meal_type": l.meal_type,
                "food_name": l.food_name,
                "calories": round(float(l.calories or 0.0), 1),
                "protein": round(float(l.protein or 0.0), 1),
                "carbs": round(float(l.carbs or 0.0), 1),
                "fat": round(float(l.fat or 0.0), 1)
            }
            for l in logs
        ]
    }


@api.delete("/api/meal-logs/{log_id}")
def delete_meal_log(log_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Delete a specific meal log entry."""
    db_log = db.query(models.MealLog).filter(models.MealLog.id == log_id).first()
    if not db_log or db_log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal log entry not found.")
    owner_id, log_day = db_log.user_id, db_log.log_date
    db.delete(db_log)
    db.commit()
    sync_daily_macros(db, owner_id, log_day)
    return {"status": "success", "message": f"Deleted meal log {log_id}"}




@api.post("/api/recipes/generate-instructions")
def generate_recipe_instructions(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """Generate detailed preparation and recipe instructions using Gemini (central client)."""
    if not ai_text.any_provider():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured (set GEMINI_API_KEY or enable AI_LOCAL_FALLBACK)."
        )

    recipe_name = payload.get("recipe_name")
    ingredients = payload.get("ingredients")
    recipe_code = payload.get("recipe_code")
    
    if not recipe_name:
        raise HTTPException(status_code=400, detail="Recipe name is required.")

    # Format prompt for instructions
    prompt = f"""
    You are an expert chef and nutrition scientist.
    Please provide clear, step-by-step cooking preparation and cooking instructions for:
    Recipe Name: {recipe_name}
    Ingredients: {', '.join(ingredients) if ingredients else 'standard ingredients'}

    Format your response cleanly with numbered steps. Keep it concise, practical, and focus on healthy cooking techniques.
    """

    try:
        instructions_text, ai_source = ai_text.generate_text(prompt)

        # If it's a database recipe, save it for future lookups so we don't call the API again
        if recipe_code:
            recipe = db.query(models.Recipe).filter(models.Recipe.recipe_code == recipe_code).first()
            if recipe:
                recipe.instructions = instructions_text
                db.commit()

        return {"instructions": instructions_text, "source": ai_source}
    except ai_text.AIUnavailable as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI service unavailable: {e}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate instructions: {str(e)}"
        )


# --- AI Studio UI Integration Request Models & Endpoints ---
from pydantic import AliasChoices, BaseModel, Field
from typing import List, Optional, Dict

class CoachChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None

class DietPlanRequest(BaseModel):
    user_id: int
    # optional overrides chosen on the generator screen (several spellings accepted); profile values are the default
    goal: Optional[str] = Field(default=None, validation_alias=AliasChoices("goal", "fitness_goal", "goal_type", "goalType"))
    diet_type: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("diet_type", "diet", "dietType", "diet_preference", "dietary_preference", "diet_plan"),
    )

class RecipeGeneratorRequest(BaseModel):
    ingredients: str
    diet_type: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("diet_type", "diet", "dietType", "diet_preference", "dietary_preference"),
    )


def get_offline_coach_reply(message: str) -> str:
    msg = message.lower().strip()
    if "pringles" in msg or "chips" in msg or "junk" in msg:
        return (
            "While Pringles can technically fit into a calorie-controlled budget, they are high in processed saturated fats and sodium, while lacking fiber or protein. This makes them highly snackable and low in satiety.\n\n"
            "**🍏 Healthy Tip:** Try air-popped popcorn, spicy roasted edamame, or baked sweet potato chips instead! You get the crunch with a fraction of the processing."
        )
    elif "breakfast" in msg or "morning" in msg:
        return (
            "Here is an elite **NutriX High Protein Breakfast Recipe**:\n\n"
            "**Scrambled Tofu/Egg & Egg Whites**\n"
            "• 2 whole eggs + 100g egg whites\n"
            "• 1/2 sliced avocado for premium fats\n"
            "• 1 slice whole wheat flatbread/toast\n\n"
            "**Macros:** ~420 kcal | 35g Protein | 18g Carbs | 16g Healthy Fats.\n"
            "Provides clean, long-lasting energy for your entire day!"
        )
    elif "snack" in msg or "hungry" in msg:
        return (
            "Some excellent snacks to keep hunger at bay with high nutrient density:\n"
            "1. **Greek Yogurt with Berries**: Probiotics + antioxidants + low calorie protein.\n"
            "2. **A Handful of Almonds**: Heart-healthy monounsaturated fatty acids.\n"
            "3. **Apple Slices with Peanut Butter**: Perfect fiber + fat combo for long-lasting satiety."
        )
    elif "workout" in msg or "training" in msg or "exercise" in msg:
        return (
            "Your post-workout window is crucial for glycogen replenishment and muscle tissue recovery:\n\n"
            "**⚡ Peak Recovery Shake:**\n"
            "• 1 Scoop Pure Whey Isolate Protein (~25g protein)\n"
            "• 1 Medium Ripe Banana (fast-acting glucose to spike insulin and force aminos into muscles)\n"
            "• 250ml cold water or coconut water (rehydration electrolytes)\n\n"
            "Drink this within 45 minutes of completing your workout for gold-standard recovery!"
        )
    else:
        return (
            "That is an excellent question! Nutrition is very personalized. To give you the best advice:\n\n"
            "Focus on getting **sufficient protein (1.6g - 2.0g per kg)**, consuming **plenty of dietary fiber (25g-35g daily)**, and drinking **adequate water (3L+ daily)**.\n\n"
            "Feel free to ask specific questions about ingredients, exercise, or timing!"
        )


@api.post("/api/ai/coach")
def ai_coach(req: CoachChatRequest):
    instructions = (
        "You are 'NutriX AI Coach', a premium, highly expert smart nutrition and health assistant. "
        "You help users make incredibly healthy food choices, manage goals (like weight loss, muscle gain), "
        "and design customized nutrition plans. Be positive, encouraging, scientifically accurate, and precise. "
        "Provide actionable tips, keep answers punchy, conversational, and use styled bullets."
    )
    
    contents = []
    if req.history:
        for item in req.history:
            role = "user" if item.get("role") == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": item.get("message", "")}]
            })
    
    contents.append({
        "role": "user",
        "parts": [{"text": req.message}]
    })

    try:
        text, source = ai_text.generate_text(contents=contents, system=instructions)
        return {"reply": text, "source": source}
    except ai_text.AIUnavailable:
        return {"reply": get_offline_coach_reply(req.message), "source": "offline"}


DIET_RULES = {
    "jain": "Strictly Jain: no meat, fish or eggs, and no root vegetables (potato, onion, garlic, carrot, beetroot, radish) or mushrooms.",
    "vegan": "Strictly vegan: no meat, poultry, fish, eggs, dairy or honey.",
    "eggetarian": "Eggetarian: eggs and dairy are fine, but no meat, poultry or fish.",
    "pescatarian": "Pescatarian: fish and dairy are fine, but no meat or poultry.",
    "vegetarian": "Strictly vegetarian: no meat, poultry, fish or eggs (dairy is fine).",
    "non-vegetarian": "No dietary restrictions.",
}
GOAL_LABELS = {
    "fat loss": "weight loss (fat loss, calorie deficit)",
    "weight gain": "weight gain (calorie surplus)",
    "muscle gain": "muscle gain (high protein, small surplus)",
    "maintenance": "maintenance",
}
OFFLINE_MENUS = {
    "non-vegetarian": ("Oats with almonds and banana (~450 kcal)", "Grilled chicken breast with brown rice and broccoli (~600 kcal)",
                       "Tofu/Paneer stir-fry with mixed vegetables (~450 kcal)", "Greek yogurt with honey (~200 kcal)"),
    "vegetarian": ("Moong dal chilla with mint chutney (~350 kcal)", "Dal, 2 rotis, mixed vegetable sabzi and curd (~600 kcal)",
                   "Paneer bhurji with a roti and salad (~450 kcal)", "Roasted chana and a fruit (~200 kcal)"),
    "vegan": ("Vegetable poha with peanuts (~350 kcal)", "Rajma with brown rice and salad (~600 kcal)",
              "Tofu stir-fry with vegetables and a roti (~450 kcal)", "Roasted chickpeas and a fruit (~200 kcal)"),
    "jain": ("Moong dal chilla without onion or garlic (~350 kcal)", "Dal (no garlic), 2 rotis and lauki sabzi (~600 kcal)",
             "Paneer and capsicum sabzi with a roti (~450 kcal)", "Fruit with a handful of almonds (~200 kcal)"),
}
OFFLINE_MENUS["eggetarian"] = ("Vegetable omelette with a toast (~400 kcal)", *OFFLINE_MENUS["vegetarian"][1:])
OFFLINE_MENUS["pescatarian"] = OFFLINE_MENUS["vegetarian"][:1] + ("Grilled fish with brown rice and vegetables (~600 kcal)",) + OFFLINE_MENUS["vegetarian"][2:]


def _diet_key(value: Optional[str]) -> Optional[str]:
    """Normalise a diet wording to a DIET_RULES key (None when empty/unknown)."""
    v = (value or "").strip().lower()
    if not v or v in ("all", "any", "none"):
        return None
    if "jain" in v:
        return "jain"
    if "vegan" in v:
        return "vegan"
    if "egg" in v:
        return "eggetarian"
    if "pesc" in v:
        return "pescatarian"
    if "non" in v or "meat" in v:
        return "non-vegetarian"
    if "veg" in v:
        return "vegetarian"
    return None


def _offline_diet_plan(diet: str, goal: str, target_calories: float) -> str:
    b, l, d, s = OFFLINE_MENUS.get(diet, OFFLINE_MENUS["non-vegetarian"])
    return (f"AI Diet Plan (offline mode, {diet}, goal: {goal}):\n\nBreakfast: {b}\nLunch: {l}\nDinner: {d}\nSnacks: {s}\n\n"
            f"Adjust portions to reach about {round(target_calories)} kcal a day.")


@api.post("/api/ai/diet-plan")
def ai_diet_plan(req: DietPlanRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    goal = normalize_goal(req.goal or user.goal)
    diet = _diet_key(req.diet_type) or _diet_key(user.diet_type) or "non-vegetarian"
    age = user.age or 30
    gender = user.gender or "male"
    height = user.height or 170.0
    weight = user.weight or 70.0
    activity_level = user.activity_level or "sedentary"

    # targets for the goal that was actually requested (the stored ones belong to the profile's own goal)
    if goal == normalize_goal(user.goal) and user.target_calories and user.target_protein:
        target_calories, target_protein = float(user.target_calories), float(user.target_protein)
    else:
        t = NutritionEngine.calculate_targets(age=age, gender=gender, height=height, weight=weight,
                                              activity_level=activity_level, goal=goal)
        target_calories, target_protein = t["target_calories"], t["target_protein_g"]

    prompt = f"""
    Generate a 1-day customized nutrition diet meal plan for a person with the following statistics:
    - Goal: {GOAL_LABELS[goal]}
    - Diet type: {diet}. {DIET_RULES[diet]}
    - Age: {age} years old
    - Gender: {gender}
    - Height: {height} cm
    - Weight: {weight} kg
    - Activity Level: {activity_level}
    - Target Calories: {round(target_calories)} kcal
    - Target Protein: {round(target_protein)} g

    Provide recommendations structured in 4 meals:
    1. Breakfast
    2. Lunch
    3. Dinner
    4. Snacks

    Every meal MUST follow the diet type above: do not include any forbidden ingredient. Prefer Indian home-style foods where sensible.
    Explain briefly why this fits their specific goals. Include precise ingredients, serving sizes, and calorie counts for each meal. Make the design of output clean, readable, and energetic.
    """

    try:
        text, source = ai_text.generate_text(prompt, system="You are an elite sports dietician. Output absolute gold-standard, premium recipe planning recommendations.")
        return {"plan": text, "source": source}
    except ai_text.AIUnavailable:
        return {"plan": _offline_diet_plan(diet, goal, target_calories), "source": "offline"}


@api.post("/api/ai/recipe-generator")
def ai_recipe_generator(req: RecipeGeneratorRequest):
    """
    Returns {recipe, source, name, servings, nutrition}. `recipe` is a Markdown string for display; `name` and `nutrition`
    (per serving: calories, protein_g, carbs_g, fat_g) are structured values the app can use to log the meal. They are None when
    the model gave no usable figures, so the app should leave those fields empty instead of guessing.
    """
    diet = _diet_key(req.diet_type)
    diet_line = f"\n    The recipe MUST follow this diet: {DIET_RULES[diet]}" if diet else ""
    prompt = f"""
    I have the following ingredients:
    {req.ingredients}
    {diet_line}
    Generate a delicious, healthy, high-nutrient recipe containing these ingredients.
    Output:
    - Recipe Name
    - Cooking Difficulty
    - Total Prep & Cook Time
    - Detailed Ingredients list
    - Step-by-Step Cooking instructions (easy to follow, structured)
    - Calories & Core Macro nutrient Breakdown (Protein, Carbs, Fat) per serving
    - Health score / Benefits for fitness
    """ + recipe_nutrition.MACHINE_BLOCK_INSTRUCTION

    try:
        text, source = ai_text.generate_text(prompt, system="You are a professional chef and health nutritionist combined. Give clean, highly structured kitchen instructions.")
        parsed = recipe_nutrition.extract(text)
        return {"recipe": parsed["recipe"], "source": source, "name": parsed["name"],
                "servings": parsed["servings"], "nutrition": parsed["nutrition"]}
    except ai_text.AIUnavailable:
        return {"recipe": f"Simulated Recipe based on ingredients (Gemini API offline): {req.ingredients}\n\nRecipe Name: Healthy Homely Stir-fry\nPrep Time: 15 mins\nInstructions:\n1. Chop ingredients.\n2. Heat a non-stick pan.\n3. Toss in ingredients and stir cook for 10 minutes.",
                "source": "offline", "name": "Healthy Homely Stir-fry", "servings": None, "nutrition": None}


# =====================================================================
# DASHBOARD ENDPOINTS (new in the integrated service; canonical paths only)
# =====================================================================
def _parse_day(value: Optional[str]) -> date:
    """UTC "today" by default: the same day boundary MS1 and the DB trigger use."""
    if not value:
        return clock.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date must be YYYY-MM-DD")


@api_router.get("/api/v1/user/daily-summary")
def get_daily_summary(
    day: Optional[str] = Query(None, alias="date"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Today's totals vs targets for the dashboard rings. Redis first (<10 ms), recomputed from the DB on a miss."""
    d = _parse_day(day)
    payload = get_daily_macros(current_user.id, d.isoformat())
    source = "redis"
    # a cache entry written by an older writer (different keys) is rebuilt rather than trusted
    if not payload or "protein_g" not in payload or "meals_count" not in payload:
        payload = sync_daily_macros(db, current_user.id, d, publish=False)
        source = "db"

    targets = _user_targets(current_user)
    summary = live_stream.build_summary(targets, payload, d.isoformat(), source)
    summary["user_id"] = current_user.id
    return summary


def _user_targets(user: models.User) -> Dict[str, float]:
    return {
        "calories": float(user.target_calories or 2000.0),
        "protein_g": float(user.target_protein or 140.0),
        "carbs_g": float(user.target_carbs or 220.0),
        "fat_g": float(user.target_fat or 60.0),
    }


@api_router.get("/api/v1/user/stream")
async def stream_daily_summary(request: Request, current_user: models.User = Depends(get_current_user)):
    """
    Live dashboard feed (Server-Sent Events): the current summary immediately, then one `summary` event per change.
    Use an HTTP client that can send the Authorization header (a browser EventSource cannot).
    """
    from shared.db import SessionLocal
    user_id, targets = current_user.id, _user_targets(current_user)

    def snapshot() -> Dict[str, Any]:
        today = clock.today()
        cached = get_daily_macros(user_id, today.isoformat())
        if not cached or "protein_g" not in cached or "meals_count" not in cached:
            session = SessionLocal()
            try:
                cached = sync_daily_macros(session, user_id, today, publish=False)
            finally:
                session.close()
        return cached

    return StreamingResponse(
        live_stream.summary_stream(user_id, targets, snapshot, request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@api_router.get("/api/v1/user/history")
def get_meal_history(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Chronological meal diary (all sources: scale, manual, fast food...). Defaults to the last 7 days."""
    from datetime import timedelta
    end = _parse_day(date_to)
    start = _parse_day(date_from) if date_from else end - timedelta(days=6)
    query = db.query(models.MealLog).filter(
        models.MealLog.user_id == current_user.id,
        models.MealLog.log_date >= start,
        models.MealLog.log_date <= end,
    )
    total = query.count()
    rows = (
        query.order_by(models.MealLog.log_date.desc(), models.MealLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [
            {
                "id": m.id,
                "log_date": m.log_date.isoformat(),
                "meal_type": m.meal_type,
                "food_name": m.food_name,
                "weight_g": m.weight_g,
                "calories": round(float(m.calories or 0.0), 1),
                "protein": round(float(m.protein or 0.0), 1),
                "carbs": round(float(m.carbs or 0.0), 1),
                "fat": round(float(m.fat or 0.0), 1),
                "source": m.source,
            }
            for m in rows
        ],
    }


@api_router.get("/api/v1/user/targets", response_model=schemas.UserProfileResponse)
def get_my_targets(current_user: models.User = Depends(get_current_user)):
    """The caller's profile with BMR/TDEE-based targets (no user id in the URL)."""
    return format_user_profile(current_user)
