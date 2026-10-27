from typing import Optional

from pydantic import BaseModel, Field


class NutritionPer100g(BaseModel):
    calories: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)


class VisionInferResponse(BaseModel):
    food_name: str
    confidence: Optional[float] = None
    per_100g: Optional[NutritionPer100g] = None
    source: str = "qwen3-vl-2b"
    latency_ms: int = 0
    flagged: bool = False
    flag_reason: Optional[str] = None


class LookupRequest(BaseModel):
    food_name: str = Field(min_length=1, max_length=200)


class LookupResponse(BaseModel):
    food_name: str
    per_100g: Optional[NutritionPer100g] = None
    source: str  # "db" | "qwen3-vl-2b"
    latency_ms: int = 0
    flagged: bool = False
    flag_reason: Optional[str] = None
