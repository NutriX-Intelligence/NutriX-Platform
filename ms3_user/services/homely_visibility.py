"""
Who sees which homely meal. One place for the rule, used by the routes, the recommender and the meal planner.

For a viewer (a user id) every homely meal is exactly one of:

  mine      the viewer created it. Always theirs ("My Recipes"), whatever other users decide.
  pending   shared with the community, the viewer has not decided yet.
  approved  shared, and the viewer approved it (or it is curated: status 'approved' and the viewer has not rejected it).
  rejected  shared, and the viewer rejected it. Hidden from them only.
  (none)    someone else's private meal (is_community = false): invisible to the viewer.

Decisions are per user (homely_meal_decisions). `HomelyMeal.status` is never changed by a user's decision: 'approved'
means curated for everyone (the seeded meals), 'pending' means "shared, awaiting each user's decision".
"""
from typing import Dict, Iterable, Optional

from sqlalchemy import and_, exists, not_, or_

from shared.models import HomelyMeal, HomelyMealDecision


def _decision_by(viewer_id: Optional[int], decision: Optional[str] = None):
    cond = [HomelyMealDecision.meal_id == HomelyMeal.id, HomelyMealDecision.user_id == viewer_id]
    if decision:
        cond.append(HomelyMealDecision.decision == decision)
    return exists().where(*cond)


def is_mine(viewer_id: Optional[int]):
    return HomelyMeal.creator_id == viewer_id


def _shared_by_someone_else(viewer_id: Optional[int]):
    return and_(HomelyMeal.is_community.is_(True), or_(HomelyMeal.creator_id.is_(None), HomelyMeal.creator_id != viewer_id))


def is_pending_for(viewer_id: Optional[int]):
    return and_(_shared_by_someone_else(viewer_id), HomelyMeal.status == "pending", not_(_decision_by(viewer_id)))


def is_approved_for(viewer_id: Optional[int]):
    """Someone else's shared meal that the viewer may use (their own meals are `is_mine`)."""
    return and_(
        _shared_by_someone_else(viewer_id),
        or_(
            _decision_by(viewer_id, "approved"),
            and_(HomelyMeal.status == "approved", not_(_decision_by(viewer_id))),
        ),
    )


def is_rejected_for(viewer_id: Optional[int]):
    return and_(
        _shared_by_someone_else(viewer_id),
        or_(
            _decision_by(viewer_id, "rejected"),
            and_(HomelyMeal.status == "rejected", not_(_decision_by(viewer_id))),
        ),
    )


def is_usable_by(viewer_id: Optional[int]):
    """Mine + approved for the viewer: what search, recommendations, the planner and the builder may offer."""
    return or_(is_mine(viewer_id), is_approved_for(viewer_id))


def decisions_for(db, viewer_id: Optional[int], meal_ids: Iterable[int]) -> Dict[int, str]:
    """{meal_id: 'approved'|'rejected'} for the viewer's own decisions on these meals (one query)."""
    ids = list(meal_ids)
    if viewer_id is None or not ids:
        return {}
    rows = db.query(HomelyMealDecision.meal_id, HomelyMealDecision.decision).filter(
        HomelyMealDecision.user_id == viewer_id, HomelyMealDecision.meal_id.in_(ids)
    ).all()
    return {meal_id: decision for meal_id, decision in rows}


def viewer_status(meal: HomelyMeal, viewer_id: Optional[int], decisions: Dict[int, str]) -> str:
    """'approved' | 'pending' | 'rejected' as this viewer sees the meal (their own meals read 'approved')."""
    if viewer_id is not None and meal.creator_id == viewer_id:
        return "approved"
    return decisions.get(meal.id) or meal.status or "pending"
