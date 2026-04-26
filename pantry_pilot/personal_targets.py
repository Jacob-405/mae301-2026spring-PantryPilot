from __future__ import annotations

from dataclasses import dataclass

from pantry_pilot.models import PersonalNutritionTargets, UserNutritionProfile
from pantry_pilot.normalization import normalize_name


ACTIVITY_COEFFICIENTS = {
    "female": {
        "sedentary": 1.0,
        "low_active": 1.12,
        "active": 1.27,
        "very_active": 1.45,
    },
    "male": {
        "sedentary": 1.0,
        "low_active": 1.11,
        "active": 1.25,
        "very_active": 1.48,
    },
}
GOAL_CALORIE_ADJUSTMENTS = {
    "maintain": 0,
    "mild deficit": -250,
    "mild surplus": 250,
    "high protein preference": 0,
}
MYPLATE_TARGET_TABLE = (
    {
        "calories": 1600,
        "produce_cups": 3.5,
        "grains_ounces": 5.0,
        "protein_foods_ounces": 5.0,
        "dairy_cups": 3.0,
    },
    {
        "calories": 1800,
        "produce_cups": 4.0,
        "grains_ounces": 6.0,
        "protein_foods_ounces": 5.0,
        "dairy_cups": 3.0,
    },
    {
        "calories": 2000,
        "produce_cups": 4.5,
        "grains_ounces": 6.0,
        "protein_foods_ounces": 5.5,
        "dairy_cups": 3.0,
    },
    {
        "calories": 2200,
        "produce_cups": 5.0,
        "grains_ounces": 7.0,
        "protein_foods_ounces": 6.0,
        "dairy_cups": 3.0,
    },
    {
        "calories": 2400,
        "produce_cups": 5.5,
        "grains_ounces": 8.0,
        "protein_foods_ounces": 6.5,
        "dairy_cups": 3.0,
    },
    {
        "calories": 2800,
        "produce_cups": 6.0,
        "grains_ounces": 9.0,
        "protein_foods_ounces": 7.0,
        "dairy_cups": 3.0,
    },
)


@dataclass(frozen=True)
class TargetSummary:
    calorie_target_text: str
    macro_target_text: str
    food_group_target_text: str
    guidance_note: str


def generate_personal_targets(
    profile: UserNutritionProfile,
    *,
    meals_per_day: int,
) -> PersonalNutritionTargets:
    sex = _normalized_sex(profile.sex)
    activity_level = _normalized_activity_level(profile.activity_level)
    goal = _normalized_goal(profile.planning_goal)
    estimated_daily_calories = round(_estimated_energy_requirement(profile, sex=sex, activity_level=activity_level))
    adjusted_calories = max(1200, estimated_daily_calories + GOAL_CALORIE_ADJUSTMENTS[goal])
    calorie_half_range = max(150, meals_per_day * 75)
    calorie_target_min = max(1200, adjusted_calories - calorie_half_range)
    calorie_target_max = calorie_target_min + (calorie_half_range * 2)

    protein_target_min = max((0.8 if goal != "high protein preference" else 1.2) * profile.weight_kg, adjusted_calories * 0.15 / 4)
    protein_target_max = max(protein_target_min + 20.0, adjusted_calories * (0.35 if goal == "high protein preference" else 0.3) / 4)
    carbs_ratio_min = 0.45
    carbs_ratio_max = 0.55 if goal == "high protein preference" else 0.60
    fat_ratio_min = 0.20
    fat_ratio_max = 0.30 if goal == "high protein preference" else 0.35
    carbs_target_min = adjusted_calories * carbs_ratio_min / 4
    carbs_target_max = adjusted_calories * carbs_ratio_max / 4
    fat_target_min = adjusted_calories * fat_ratio_min / 9
    fat_target_max = adjusted_calories * fat_ratio_max / 9

    food_group_targets = _myplate_targets_for_calories(adjusted_calories)
    guidance_note = (
        "Estimated planning guidance from adult energy-reference logic, DRI-style macro ranges, and MyPlate-style food-group targets. "
        "This is for meal planning support, not medical advice."
    )
    return PersonalNutritionTargets(
        source="dri-myplate-estimate",
        guidance_note=guidance_note,
        estimated_daily_calories=adjusted_calories,
        calorie_target_min=int(calorie_target_min),
        calorie_target_max=int(calorie_target_max),
        protein_target_min_grams=round(protein_target_min, 1),
        protein_target_max_grams=round(protein_target_max, 1),
        carbs_target_min_grams=round(carbs_target_min, 1),
        carbs_target_max_grams=round(carbs_target_max, 1),
        fat_target_min_grams=round(fat_target_min, 1),
        fat_target_max_grams=round(fat_target_max, 1),
        produce_target_cups=food_group_targets["produce_cups"],
        grains_target_ounces=food_group_targets["grains_ounces"],
        protein_foods_target_ounces=food_group_targets["protein_foods_ounces"],
        dairy_target_cups=food_group_targets["dairy_cups"],
    )


def targets_from_manual_calorie_range(minimum: int, maximum: int) -> PersonalNutritionTargets:
    midpoint = round((minimum + maximum) / 2)
    carbs_target_min = midpoint * 0.45 / 4
    carbs_target_max = midpoint * 0.60 / 4
    fat_target_min = midpoint * 0.20 / 9
    fat_target_max = midpoint * 0.35 / 9
    protein_target_min = max(50.0, midpoint * 0.15 / 4)
    protein_target_max = max(protein_target_min + 20.0, midpoint * 0.30 / 4)
    food_group_targets = _myplate_targets_for_calories(midpoint)
    return PersonalNutritionTargets(
        source="manual-calorie-guidance",
        guidance_note="Estimated planning guidance from the selected calorie range and MyPlate-style food-group targets.",
        estimated_daily_calories=midpoint,
        calorie_target_min=minimum,
        calorie_target_max=maximum,
        protein_target_min_grams=round(protein_target_min, 1),
        protein_target_max_grams=round(protein_target_max, 1),
        carbs_target_min_grams=round(carbs_target_min, 1),
        carbs_target_max_grams=round(carbs_target_max, 1),
        fat_target_min_grams=round(fat_target_min, 1),
        fat_target_max_grams=round(fat_target_max, 1),
        produce_target_cups=food_group_targets["produce_cups"],
        grains_target_ounces=food_group_targets["grains_ounces"],
        protein_foods_target_ounces=food_group_targets["protein_foods_ounces"],
        dairy_target_cups=food_group_targets["dairy_cups"],
    )


def summarize_targets(targets: PersonalNutritionTargets | None) -> TargetSummary | None:
    if targets is None:
        return None
    calorie_text = (
        f"{targets.calorie_target_min:,} to {targets.calorie_target_max:,} calories/day"
    )
    macro_text = (
        f"Protein {targets.protein_target_min_grams:.0f}-{targets.protein_target_max_grams:.0f}g, "
        f"carbs {targets.carbs_target_min_grams:.0f}-{targets.carbs_target_max_grams:.0f}g, "
        f"fat {targets.fat_target_min_grams:.0f}-{targets.fat_target_max_grams:.0f}g"
    )
    food_group_bits = [
        f"produce {targets.produce_target_cups:.1f} cups",
        f"grains/starches {targets.grains_target_ounces:.1f} oz",
        f"protein foods {targets.protein_foods_target_ounces:.1f} oz",
    ]
    if targets.dairy_target_cups is not None:
        food_group_bits.append(f"dairy/alternatives {targets.dairy_target_cups:.1f} cups")
    return TargetSummary(
        calorie_target_text=calorie_text,
        macro_target_text=macro_text,
        food_group_target_text=", ".join(food_group_bits),
        guidance_note=targets.guidance_note,
    )


def _estimated_energy_requirement(
    profile: UserNutritionProfile,
    *,
    sex: str,
    activity_level: str,
) -> float:
    height_meters = profile.height_cm / 100
    pa = ACTIVITY_COEFFICIENTS[sex][activity_level]
    if sex == "male":
        return 662 - (9.53 * profile.age_years) + pa * ((15.91 * profile.weight_kg) + (539.6 * height_meters))
    return 354 - (6.91 * profile.age_years) + pa * ((9.36 * profile.weight_kg) + (726 * height_meters))


def _myplate_targets_for_calories(calories: int) -> dict[str, float]:
    closest = min(
        MYPLATE_TARGET_TABLE,
        key=lambda row: abs(row["calories"] - calories),
    )
    return {
        "produce_cups": float(closest["produce_cups"]),
        "grains_ounces": float(closest["grains_ounces"]),
        "protein_foods_ounces": float(closest["protein_foods_ounces"]),
        "dairy_cups": float(closest["dairy_cups"]),
    }


def _normalized_sex(value: str) -> str:
    normalized = normalize_name(value)
    if normalized in {"male", "man"}:
        return "male"
    return "female"


def _normalized_activity_level(value: str) -> str:
    normalized = normalize_name(value)
    if normalized in {"sedentary", "low active", "low_active", "active", "very active", "very_active"}:
        return normalized.replace(" ", "_")
    return "low_active"


def _normalized_goal(value: str) -> str:
    normalized = normalize_name(value)
    if normalized in GOAL_CALORIE_ADJUSTMENTS:
        return normalized
    return "maintain"
