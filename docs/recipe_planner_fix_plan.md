# PantryPilot Recipe Planner Fix Plan

## Revised Phase Order

1. Phase 0 - Baseline and active data path
2. Phase 1 - Dataset path verification closeout
3. Phase 2 - Fix unknown metadata being treated as zero
4. Phase 3 - Make calorie target and weekly budget materially affect planning
5. Phase 4 - Filter out non-meals from breakfast/lunch/dinner
6. Phase 5 - Add a supporting nutrition/cost layer only if still needed after Phases 2-4
7. Phase 6 - Add regression tests and fast demo checks
8. Phase 7 - MAE301 compliance audit

## Phase 0 - Baseline and active data path

### Status

PASS

### Goal

- Confirm which processed recipe file the planner actually loads
- Reproduce the current failures with a small, repeatable example set
- Establish a baseline before changing code

### Root Cause Findings So Far

- The planner is using the full RecipeNLG processed dataset in normal operation.
- The current default dataset path is `mvp/data/processed/recipenlg-full-20260416T0625Z.json`.
- The active dataset-path issue is not the current cause of the observed failures.
- All loaded RecipeNLG recipes currently arrive with `estimated_calories_per_serving == 0`.
- All loaded RecipeNLG recipes currently arrive with `prep_time_minutes == 0`.
- The processed RecipeNLG JSON still carries unknown calories as `{"calories_per_serving": null, ...}`, but the current loader collapses those unknown values to `0`.
- The planner currently allows sauce/dip/relish-style recipes into `dinner` and other meal slots because it trusts imported `meal_types` and does not apply a meal-reasonableness filter.
- Budget pressure is currently blunted because many shopping-list ingredients are effectively free:
  - some are `unpriced`
  - some cost `0.0` because package purchase conversion fails and the pricing layer returns zero cost
- Calorie targets appear ignored in reproduced runs because all candidate meals carry `0` calories after loading, so different calorie targets generate the same plan.

### Files Inspected

- `pantry_pilot/providers.py`
- `pantry_pilot/planner.py`
- `pantry_pilot/models.py`
- `pantry_pilot/sample_data.py`
- `mvp/app.py`
- `mvp/data/processed/recipenlg-full-20260416T0625Z.json`

### Active Dataset Path

- Confirmed active planner dataset path:
  - `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
- Confirmed loaded recipe count:
  - `23021`

### Reproduced Failures

#### Failure 1 - Zero calories and zero prep time in loaded RecipeNLG recipes

Verification command:

```powershell
.\.venv\Scripts\python.exe -c "from pantry_pilot.providers import DEFAULT_PROCESSED_RECIPES_PATH, LocalRecipeProvider; recipes=LocalRecipeProvider().list_recipes(); print('DATASET', DEFAULT_PROCESSED_RECIPES_PATH); print('COUNT', len(recipes)); zero=[r for r in recipes if r.estimated_calories_per_serving==0]; print('ZERO_CALORIES', len(zero)); print('ZERO_EXAMPLES', [r.title for r in zero[:15]])"
```

Verification output:

```text
DATASET mvp\data\processed\recipenlg-full-20260416T0625Z.json
COUNT 23021
ZERO_CALORIES 23021
ZERO_EXAMPLES ['" Add In Anything" Muffins!', '" Yummy N\' Easiest" Warm Blueberry Sauce', '"Amish" Friendship Bread', '"Apple Cake"', '"Apple Crisp" Peanut Butter Snack Bites', '"Bestest" Baked Doughnuts', '"Big Apple" Pancakes', '"Blondie" Bars With Peanut Butter Filled Delightfulls™', '"Blondie" Bars With Peanut Butter Filled Delightfulls™', '"Blondie" Brownies', '"Breakfast" Casserole', '"Candy Nuts"', '"Cocktail Meatballs"', '"Comforts" For Cozy Times(Quick And Easy)', '"Creek" Indian Fry Bread(Tuklegg Sahkmoohlthie)']
```

Additional verification command:

```powershell
.\.venv\Scripts\python.exe -c "from pantry_pilot.providers import LocalRecipeProvider; recipes=LocalRecipeProvider().list_recipes(); prep0=sum(1 for r in recipes if r.prep_time_minutes==0); print('PREP_ZERO', prep0); print('PREP_ZERO_EXAMPLES', [r.title for r in recipes if r.prep_time_minutes==0][:15])"
```

Verification output:

```text
PREP_ZERO 23021
PREP_ZERO_EXAMPLES ['" Add In Anything" Muffins!', '" Yummy N\' Easiest" Warm Blueberry Sauce', '"Amish" Friendship Bread', '"Apple Cake"', '"Apple Crisp" Peanut Butter Snack Bites', '"Bestest" Baked Doughnuts', '"Big Apple" Pancakes', '"Blondie" Bars With Peanut Butter Filled Delightfulls™', '"Blondie" Bars With Peanut Butter Filled Delightfulls™', '"Blondie" Brownies', '"Breakfast" Casserole', '"Candy Nuts"', '"Cocktail Meatballs"', '"Comforts" For Cozy Times(Quick And Easy)', '"Creek" Indian Fry Bread(Tuklegg Sahkmoohlthie)']
```

Representative raw-row verification:

```powershell
.\.venv\Scripts\python.exe -c "import json; from pathlib import Path; p=Path('mvp/data/processed/recipenlg-full-20260416T0625Z.json'); data=json.loads(p.read_text(encoding='utf-8')); titles=['Garlic Aioli (Dipping Sauce for French Fries)','Authentic Mexican Guacamole','Indian Onion Relish']; \
for row in data['recipes']: \
    if row.get('title') in titles: \
        print(row['title'], {'prep_time_minutes': row.get('prep_time_minutes'), 'calories': row.get('calories'), 'meal_types': row.get('meal_types'), 'ingredients': len(row.get('ingredients',[]))})"
```

Verification output:

```text
Authentic Mexican Guacamole {'prep_time_minutes': 0, 'calories': {'calories_per_serving': None, 'source': '', 'confidence': None, 'notes': ''}, 'meal_types': ['dinner'], 'ingredients': 4}
Garlic Aioli (Dipping Sauce for French Fries) {'prep_time_minutes': 0, 'calories': {'calories_per_serving': None, 'source': '', 'confidence': None, 'notes': ''}, 'meal_types': ['dinner'], 'ingredients': 4}
Indian Onion Relish {'prep_time_minutes': 0, 'calories': {'calories_per_serving': None, 'source': '', 'confidence': None, 'notes': ''}, 'meal_types': ['dinner'], 'ingredients': 4}
```

#### Failure 2 - Changing weekly budget has little or no effect

Verification command:

```powershell
.\.venv\Scripts\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.planner import WeeklyMealPlanner; planner=WeeklyMealPlanner(); \
base=dict(servings=2,cuisine_preferences=(),allergies=(),excluded_ingredients=(),diet_restrictions=(),pantry_staples=(),max_prep_time_minutes=35,meals_per_day=1,meal_structure=('dinner',),pricing_mode='mock',daily_calorie_target_min=1600,daily_calorie_target_max=2200,variety_preference='balanced',leftovers_mode='off'); \
for budget in (40.0,80.0): \
 r=PlannerRequest(weekly_budget=budget,**base); p=planner.create_plan(r); print('BUDGET',budget,'TOTAL',p.estimated_total_cost,'MEALS',[m.recipe.title for m in p.meals])"
```

Verification output:

```text
BUDGET 40.0 TOTAL 2.4 MEALS ['Apple Waldorf Salad', 'Garlic Aioli (Dipping Sauce for French Fries)', 'Italian Sauced Chicken', 'Indian Onion Relish', 'Authentic Mexican Guacamole', 'Mediterranean Caesar Salad', 'Crock Pot Pineapple Chicken']
BUDGET 80.0 TOTAL 2.4 MEALS ['Apple Waldorf Salad', 'Garlic Aioli (Dipping Sauce for French Fries)', 'Italian Sauced Chicken', 'Indian Onion Relish', 'Authentic Mexican Guacamole', 'Mediterranean Caesar Salad', 'Crock Pot Pineapple Chicken']
```

Supporting shopping-list verification:

```powershell
.\.venv\Scripts\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.planner import WeeklyMealPlanner; planner=WeeklyMealPlanner(); request=PlannerRequest(weekly_budget=40.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',), pricing_mode='mock', daily_calorie_target_min=1600, daily_calorie_target_max=2200, variety_preference='balanced', leftovers_mode='off'); plan=planner.create_plan(request); print('MEALS', [m.recipe.title for m in plan.meals]); print('SHOPPING', [(i.name, i.quantity, i.unit, i.estimated_cost, i.pricing_source) for i in plan.shopping_list]); print('TOTAL', plan.estimated_total_cost)"
```

Verification output:

```text
MEALS ['Apple Waldorf Salad', 'Garlic Aioli (Dipping Sauce for French Fries)', 'Italian Sauced Chicken', 'Indian Onion Relish', 'Authentic Mexican Guacamole', 'Mediterranean Caesar Salad', 'Crock Pot Pineapple Chicken']
SHOPPING [('apple', 2.5, 'cup', 0.0, 'mock'), ('avocado', 1.0, 'item', 0.9, 'mock'), ('cayenne pepper', 0.25, 'tsp', None, 'unpriced'), ('chicken breast', 3.0, 'item', 0.0, 'mock'), ('cilantro', 1.0, 'tbsp', None, 'unpriced'), ('garlic', 5.5, 'tsp', 0.0, 'mock'), ('green onion', 0.62, 'cup', None, 'unpriced'), ('lemon juice', 4.12, 'tbsp', None, 'unpriced'), ('mayonnaise', 0.5, 'cup', None, 'unpriced'), ('mozzarella cheese', 1.0, 'item', 0.0, 'mock'), ('onion', 1.0, 'item', 0.7, 'mock'), ('paprika', 0.5, 'item', 0.0, 'mock'), ('pineapple', 0.5, 'item', 0.0, 'mock'), ('raisins', 0.5, 'cup', None, 'unpriced'), ('tomato', 1.0, 'item', 0.8, 'mock'), ('walnuts', 0.25, 'cup', None, 'unpriced')]
TOTAL 2.4
```

#### Failure 3 - Sauce/dip/snack recipes appear in full meal slots

Verification command:

```powershell
.\.venv\Scripts\python.exe -c "from pantry_pilot.providers import LocalRecipeProvider; recipes=LocalRecipeProvider().list_recipes(); bad=[]; keywords=('dip','dips','sauce','salsa','dressing','condiment','jam','jelly','gravy','marinade','spread'); \
for r in recipes: \
    title=r.title.lower(); \
    if any(k in title for k in keywords): \
        bad.append((r.title,r.meal_types,r.estimated_calories_per_serving,r.prep_time_minutes)); \
print('BAD_TITLE_COUNT', len(bad)); print('BAD_TITLE_EXAMPLES', bad[:40])"
```

Verification output:

```text
BAD_TITLE_COUNT 2224
BAD_TITLE_EXAMPLES [('" Yummy N\' Easiest" Warm Blueberry Sauce', ('dinner',), 0, 0), ('"Dare to be Different " Dip', ('dinner',), 0, 0), ('"Dippin Apples"', ('dinner',), 0, 0), ('"Guacamole Dip"', ('dinner',), 0, 0), ('"Hot Fudge Sauce"', ('dinner',), 0, 0), ('"Hot Onion Dip"', ('dinner',), 0, 0), ('"Mom\'S" Chocolate Gravy', ('dinner',), 0, 0), ('"Novak" Salad Dressing', ('lunch', 'dinner'), 0, 0), ('"Skordalia" Garlic Sauce', ('dinner',), 0, 0), ('*Meatballs With Gravy("Chiofti Cu Culeas")', ('dinner',), 0, 0), ('1-2-3 Fruit Sauce', ('dinner',), 0, 0), ('10 Minute Fudge Sauce', ('dinner',), 0, 0), ('95 House Dressing', ('dinner',), 0, 0), ('Absolutely-Better-Than-O-Garden Alfredo Sauce', ('dinner',), 0, 0), ('Acquasale (Sweet Pepper Sauce)', ('dinner',), 0, 0), ('Alfredo Sauce', ('dinner',), 0, 0), ('Alfredo Sauce', ('dinner',), 0, 0), ('Alfredo Sauce Thin Or Thick', ('dinner',), 0, 0), ('Alfredo with cream cheese sauce', ('dinner',), 0, 0), ('All Purpose Asian Style Sauce', ('dinner',), 0, 0), ('Aloha Dip', ('dinner',), 0, 0), ('Aloha Dip', ('dinner',), 0, 0), ('Aloha Sauce For Fruit Salad', ('lunch', 'dinner'), 0, 0), ('Amaretto Fruit Dip', ('dinner',), 0, 0), ('Amazing Pork Chop Or Chicken Marinade', ('dinner',), 0, 0), ('Amish Cooked Salad Dressing', ('lunch', 'dinner'), 0, 0), ('An Apple Condiment', ('dinner',), 0, 0), ("Annetta's Hot Fudge Sauce", ('dinner',), 0, 0), ('Another Excellent Yogurt Sauce', ('dinner',), 0, 0), ('Any Meat Marinade', ('dinner',), 0, 0), ('Apple And Banana Sauce', ('dinner',), 0, 0), ('Apple Caramel Dip', ('dinner',), 0, 0), ('Apple Caramel Dip', ('dinner',), 0, 0), ('Apple Caramel Dip', ('dinner',), 0, 0), ('Apple Cream Cheese Spread', ('dinner',), 0, 0), ('Apple Dip', ('dinner',), 0, 0), ('Apple Dip', ('dinner',), 0, 0), ('Apple Dip', ('dinner',), 0, 0), ('Apple Dip', ('dinner',), 0, 0), ('Apple Dip', ('dinner',), 0, 0)]
```

Direct planner-run evidence:

```text
Selected dinner plan includes:
- Garlic Aioli (Dipping Sauce for French Fries)
- Indian Onion Relish
- Authentic Mexican Guacamole
```

#### Additional Baseline Repro - Calorie target changes do not change plan output

Verification command:

```powershell
.\.venv\Scripts\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.planner import WeeklyMealPlanner; planner=WeeklyMealPlanner(); \
base=dict(weekly_budget=80.0,servings=2,cuisine_preferences=(),allergies=(),excluded_ingredients=(),diet_restrictions=(),pantry_staples=(),max_prep_time_minutes=35,meals_per_day=1,meal_structure=('dinner',),pricing_mode='mock',variety_preference='balanced',leftovers_mode='off'); \
for lo,hi in ((1200,1600),(2600,3200)): \
 r=PlannerRequest(daily_calorie_target_min=lo,daily_calorie_target_max=hi,**base); p=planner.create_plan(r); print('CAL',lo,hi,'TOTAL',p.estimated_total_cost,'DAILY',[m.recipe.estimated_calories_per_serving*m.scaled_servings for m in p.meals],'MEALS',[m.recipe.title for m in p.meals])"
```

Verification output:

```text
CAL 1200 1600 TOTAL 2.4 DAILY [0, 0, 0, 0, 0, 0, 0] MEALS ['Apple Waldorf Salad', 'Garlic Aioli (Dipping Sauce for French Fries)', 'Italian Sauced Chicken', 'Indian Onion Relish', 'Authentic Mexican Guacamole', 'Mediterranean Caesar Salad', 'Crock Pot Pineapple Chicken']
CAL 2600 3200 TOTAL 2.4 DAILY [0, 0, 0, 0, 0, 0, 0] MEALS ['Apple Waldorf Salad', 'Garlic Aioli (Dipping Sauce for French Fries)', 'Italian Sauced Chicken', 'Indian Onion Relish', 'Authentic Mexican Guacamole', 'Mediterranean Caesar Salad', 'Crock Pot Pineapple Chicken']
```

### Files Changed

- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
+# PantryPilot Recipe Planner Fix Plan
+
+## Phase 0 - Baseline and active data path
+...
```

### Verification Result

- Active dataset path confirmed: yes
- Planner loads full RecipeNLG dataset: yes
- Three required failures reproduced: yes
- Failures are reproducible with small direct Python commands: yes

### Recommended Next Step

- Proceed to **Phase 1 - Dataset path verification closeout**
- Expected outcome for Phase 1:
  - `NO CODE CHANGE` unless a hidden older fallback path still takes precedence in normal operation
  - otherwise move to Phase 2, because unknown metadata collapsing to zero is the next real blocker

## Phase 1 - Dataset path verification closeout

### Status

PASS

### Root Cause Found

- No hidden older or smaller processed dataset path takes precedence in normal operation.
- `WeeklyMealPlanner()` constructs `LocalRecipeProvider()` with no override, and that provider defaults to `mvp/data/processed/recipenlg-full-20260416T0625Z.json`.
- The only runtime fallback is `sample_recipes()` in `LocalRecipeProvider.list_recipes()`, and it is only used when the configured processed dataset path is missing, unreadable, malformed, or yields no valid processed recipes.
- That fallback is not taking precedence in normal operation with the current working tree and the verified full RecipeNLG file present.

### Files Inspected

- `pantry_pilot/providers.py`
- `pantry_pilot/planner.py`
- `mvp/app.py`
- `mvp/README.md`
- `mvp/report.md`

### Files Changed

- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
+## Phase 1 - Dataset path verification closeout
+
+### Status
+
+PASS
+
+### Root Cause Found
+
+- No hidden older or smaller processed dataset path takes precedence in normal operation.
+...
```

### Verification Command(s)

```powershell
rg -n "DEFAULT_PROCESSED_RECIPES_PATH|LocalRecipeProvider\(|sample_recipes\(|recipes\.imported\.json|recipenlg-full-20260416T0625Z|processed_dataset_path|load_processed_recipes\(" pantry_pilot mvp tests
```

```powershell
.\.venv\Scripts\python.exe -c "from pantry_pilot.providers import DEFAULT_PROCESSED_RECIPES_PATH, LocalRecipeProvider; from pantry_pilot.planner import WeeklyMealPlanner; p=LocalRecipeProvider(); w=WeeklyMealPlanner(); print('DEFAULT', DEFAULT_PROCESSED_RECIPES_PATH); print('PROVIDER_PATH', p.processed_dataset_path); print('PLANNER_PROVIDER_PATH', w.recipe_provider.processed_dataset_path); print('LOADED', len(p.list_recipes()))"
```

### Verification Result

- `DEFAULT mvp\data\processed\recipenlg-full-20260416T0625Z.json`
- `PROVIDER_PATH mvp\data\processed\recipenlg-full-20260416T0625Z.json`
- `PLANNER_PROVIDER_PATH mvp\data\processed\recipenlg-full-20260416T0625Z.json`
- `LOADED 23021`
- The only normal runtime fallback found is `sample_recipes()` in `pantry_pilot/providers.py`, and it is conditional on processed-dataset load failure, not a higher-precedence path.

### Recommended Next Phase

- Proceed to **Phase 2 - Fix unknown metadata being treated as zero**

## Phase 2 - Fix unknown metadata being treated as zero

### Status

PASS

### Root Cause Found

- Unknown calories were being collapsed to `0` in `pantry_pilot/providers.py` by `_load_processed_calories()`.
- Unknown prep time from the full RecipeNLG processed dataset was already stored as `0` in the processed JSON and was being loaded as if it were a real prep-time value.
- Unresolved shopping-list costs were being surfaced as `0.0` when a grocery item existed in the mock catalog but unit conversion failed, even though the cost was actually unknown.
- These zeroes were then visible in the planner output and reproduced examples, making unknown metadata look valid.

### Files Inspected

- `pantry_pilot/models.py`
- `pantry_pilot/providers.py`
- `pantry_pilot/planner.py`
- `pantry_pilot/favorites.py`
- `tests/test_phase2_providers.py`
- `tests/test_phase5_pricing.py`

### Files Changed

- `pantry_pilot/models.py`
- `pantry_pilot/providers.py`
- `pantry_pilot/planner.py`
- `tests/test_phase2_providers.py`
- `tests/test_phase5_pricing.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/models.py b/pantry_pilot/models.py
@@
-    estimated_calories_per_serving: int
-    prep_time_minutes: int
+    estimated_calories_per_serving: int | None
+    prep_time_minutes: int | None
```

```diff
diff --git a/pantry_pilot/providers.py b/pantry_pilot/providers.py
@@
-        prep_time_minutes = int(row["prep_time_minutes"])
+        prep_time_minutes = _load_processed_prep_time(row.get("prep_time_minutes"))
@@
-def _load_processed_calories(value: object) -> int:
+def _load_processed_prep_time(value: object) -> int | None:
+    try:
+        prep_time = int(value)
+    except (TypeError, ValueError):
+        return None
+    if prep_time <= 0:
+        return None
+    return prep_time
+
+def _load_processed_calories(value: object) -> int | None:
@@
-        return 0
+        return None
@@
-        return 0
-    return max(calories, 0)
+        return None
+    if calories < 0:
+        return None
+    return calories
```

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
-            if recipe.prep_time_minutes > request.max_prep_time_minutes:
+            if recipe.prep_time_minutes is not None and recipe.prep_time_minutes > request.max_prep_time_minutes:
@@
+        if recipe.estimated_calories_per_serving is None:
+            return 0
         return recipe.estimated_calories_per_serving * servings
@@
-            total += cost
+            total += 0.0 if cost is None else cost
@@
-                    estimated_cost=round(cost, 2) if product is not None and product.package_price is not None else None,
+                    estimated_cost=None if cost is None else round(cost, 2),
@@
-        return cost
+        return 0.0 if cost is None else cost
@@
-    ) -> tuple[int, float, float]:
+    ) -> tuple[int, float, float | None]:
@@
-            return 0, 0.0, 0.0
+            return 0, 0.0, None
@@
-            return 0, 0.0, 0.0
+            return 0, 0.0, None
```

```diff
diff --git a/tests/test_phase2_providers.py b/tests/test_phase2_providers.py
@@
+    def test_processed_dataset_preserves_unknown_calories_and_prep_time(self) -> None:
+        ...
+            self.assertIsNone(recipe.estimated_calories_per_serving)
+            self.assertIsNone(recipe.prep_time_minutes)
```

```diff
diff --git a/tests/test_phase5_pricing.py b/tests/test_phase5_pricing.py
@@
+    def test_unknown_conversion_cost_does_not_show_as_zero(self) -> None:
+        ...
+        self.assertIsNone(apple.estimated_cost)
+        self.assertEqual(total_cost, 0.0)
```

### Verification Command(s)

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_phase2_providers.Phase2ProviderTests.test_processed_dataset_preserves_unknown_calories_and_prep_time tests.test_phase5_pricing.PricingPhase5Tests.test_unknown_conversion_cost_does_not_show_as_zero
```

```powershell
.\.venv\Scripts\python.exe -c "from pantry_pilot.providers import DEFAULT_PROCESSED_RECIPES_PATH, LocalRecipeProvider; recipes=LocalRecipeProvider().list_recipes(); unknown=[r for r in recipes if r.estimated_calories_per_serving is None]; prep_unknown=[r for r in recipes if r.prep_time_minutes is None]; print('DATASET', DEFAULT_PROCESSED_RECIPES_PATH); print('COUNT', len(recipes)); print('UNKNOWN_CALORIES', len(unknown)); print('UNKNOWN_PREP', len(prep_unknown)); print('EXAMPLE', unknown[0].title, unknown[0].estimated_calories_per_serving, unknown[0].prep_time_minutes)"
```

```powershell
.\.venv\Scripts\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.planner import WeeklyMealPlanner; planner=WeeklyMealPlanner(); request=PlannerRequest(weekly_budget=40.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',), pricing_mode='mock', daily_calorie_target_min=1600, daily_calorie_target_max=2200, variety_preference='balanced', leftovers_mode='off'); plan=planner.create_plan(request); print('SHOPPING', [(i.name, i.estimated_cost, i.pricing_source) for i in plan.shopping_list]); print('CALORIES', [m.recipe.estimated_calories_per_serving for m in plan.meals]); print('PREP', [m.recipe.prep_time_minutes for m in plan.meals])"
```

### Verification Result

- Targeted tests passed:
  - `Ran 2 tests in 0.004s`
  - `OK`
- Full RecipeNLG dataset now loads with unknowns preserved:
  - `UNKNOWN_CALORIES 23021`
  - `UNKNOWN_PREP 23021`
  - example loaded recipe metadata is now `None None`, not `0 0`
- Reproduced plan now shows unknown shopping-list costs as `None` instead of fake `0.0`
- Reproduced plan now shows meal calories and prep times as `None` instead of fake zeroes

### Recommended Next Phase

- Proceed to **Phase 3 - Make calorie target and weekly budget materially affect planning**

## Phase 3 - Make calorie target and weekly budget materially affect planning

### Status

PASS

### Root Cause Found

- The planner was still treating unknown calorie metadata as usable `0` during internal candidate scoring, even after Phase 2 preserved `None` on load.
- The planner was still treating unknown ingredient pricing as budget-neutral because internal feasibility checks summed only known prices and ignored unknown-cost ingredients.
- The recipe selector only enforced the total budget ceiling after each candidate choice. It did not strongly prioritize meals that fit the remaining budget per unfilled slot, so early expensive picks could crowd out the rest of the week.
- The repeat-cap preference could override budget realism by preferring an expensive “new” meal over a cheap repeat that actually fit the remaining week.

### Files Inspected

- `pantry_pilot/planner.py`
- `tests/test_phase6_planning.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase2_providers.py`
- `tests/test_phase5_pricing.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `pantry_pilot/planner.py`
- `tests/test_phase6_planning.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
+@dataclass(frozen=True)
+class CostEstimate:
+    total_cost: float
+    unknown_item_count: int
@@
+        self._validate_constraint_support(candidates, request, pantry_inventory)
@@
+            if recipe.estimated_calories_per_serving is None:
+                continue
+            if projected_total.unknown_item_count:
+                continue
@@
+            suggested_slot_budget = self._suggested_slot_budget(...)
+            within_slot_budget = incremental_cost <= suggested_slot_budget + 1e-9
+            budget_pressure = self._budget_pressure_penalty(...)
+            effective_cost += budget_pressure * variety_profile.budget_guardrail_weight
+            sort_key = (0 if within_slot_budget else 1, ...)
@@
+        if preferred_choice is not None:
+            if preferred_choice[1] <= suggested_slot_budget + 1e-9 or fallback_choice is None or fallback_choice[1] > suggested_slot_budget + 1e-9:
+                return preferred_choice[0], preferred_choice[1], False
+        if fallback_choice is None:
+            return None
+        return fallback_choice[0], fallback_choice[1], True
@@
+    def _validate_constraint_support(...):
+        ...
+        raise PlannerError(\"No recipes with known calorie estimates ...\")
+        raise PlannerError(\"No fully priced recipes are available ...\")
```

```diff
diff --git a/tests/test_phase6_planning.py b/tests/test_phase6_planning.py
@@
+class UnknownCalorieRecipeProvider(LocalRecipeProvider):
+    ...
+
+class BudgetChoiceRecipeProvider(LocalRecipeProvider):
+    ...
+
+class UnknownPriceRecipeProvider(LocalRecipeProvider):
+    ...
@@
+    def test_weekly_budget_changes_recipe_selection_when_costs_differ(self) -> None:
+        ...
+
+    def test_unknown_calorie_data_fails_with_clear_message(self) -> None:
+        ...
+
+    def test_unknown_price_data_fails_with_clear_message(self) -> None:
+        ...
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_planning.PlanningPhase6Tests.test_daily_calorie_target_changes_recipe_selection tests.test_phase6_planning.PlanningPhase6Tests.test_weekly_budget_changes_recipe_selection_when_costs_differ tests.test_phase6_planning.PlanningPhase6Tests.test_unknown_calorie_data_fails_with_clear_message tests.test_phase6_planning.PlanningPhase6Tests.test_unknown_price_data_fails_with_clear_message tests.test_phase2_app_display tests.test_phase2_providers.Phase2ProviderTests.test_processed_dataset_preserves_unknown_calories_and_prep_time tests.test_phase5_pricing.PricingPhase5Tests.test_unknown_conversion_cost_does_not_show_as_zero
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.planner import PlannerError, WeeklyMealPlanner; planner=WeeklyMealPlanner(); request=PlannerRequest(weekly_budget=80.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',), pricing_mode='mock', daily_calorie_target_min=1600, daily_calorie_target_max=2200, variety_preference='balanced', leftovers_mode='off'); \
try: \
    planner.create_plan(request); print('FULL_DATASET_RESULT', 'unexpected success') \
except PlannerError as exc: \
    print('FULL_DATASET_RESULT', str(exc))"
```

### Verification Result

- Targeted tests passed:
  - `Ran 8 tests in 0.009s`
  - `OK`
- Verified budget-sensitive selection:
  - low weekly budget picks the cheaper dinner
  - higher weekly budget picks the calorie-better dinner
- Verified clear failure behavior:
  - unknown-calorie recipe pools now fail with a calorie-target explanation
  - unknown-price recipe pools now fail with a budget-verification explanation
- Verified current full RecipeNLG dataset behavior:
  - `FULL_DATASET_RESULT No recipes with known calorie estimates are available for dinner, so the calorie target cannot be satisfied.`

### Recommended Next Phase

- Proceed to **Phase 4 - Filter out non-meals from breakfast/lunch/dinner**

## Phase 4 - Filter out non-meals from breakfast/lunch/dinner

### Status

PASS

### Root Cause Found

- The planner trusted imported `meal_types` too literally, so RecipeNLG rows labeled as `dinner` were allowed into meal-slot selection even when the titles were clearly sauces, dips, relishes, or condiments.
- There was no meal-reasonableness check between `meal_types` matching and final slot candidate selection.
- This allowed known bad examples such as `Garlic Aioli (Dipping Sauce for French Fries)`, `Indian Onion Relish`, and `Authentic Mexican Guacamole` to qualify as dinner recipes.

### Files Inspected

- `pantry_pilot/planner.py`
- `pantry_pilot/data_pipeline/importer.py`
- `tests/test_phase6_planning.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `pantry_pilot/planner.py`
- `tests/test_phase6_planning.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
+NON_MEAL_TITLE_KEYWORDS = frozenset(
+    {
+        "aioli", "condiment", "condiments", "dip", "dips", "dressing", "dressings",
+        "gravy", "guacamole", "marinade", "marinades", "relish", "salsa",
+        "sauce", "sauces", "snack", "snacks", "spread", "spreads", "syrup", "topping",
+    }
+)
+SUBSTANTIAL_MEAL_KEYWORDS = frozenset(
+    {
+        "bake", "bowl", "breakfast", "burger", "burrito", "casserole", "chicken",
+        "chili", "curry", "dinner", "egg", "eggs", "frittata", "lunch", "meatball",
+        "meatballs", "omelet", "omelette", "pancake", "pancakes", "pasta", "plate",
+        "pizza", "roast", "salad", "sandwich", "scramble", "skillet", "soup", "stew",
+        "stir fry", "stuffed", "taco", "toast", "wrap",
+    }
+)
@@
-        return matching or candidates
+        if desired == "meal":
+            return matching or candidates
+        reasonable = tuple(recipe for recipe in matching if self._is_reasonable_meal_for_slot(recipe, desired))
+        return reasonable or matching or candidates
@@
+    def _is_reasonable_meal_for_slot(self, recipe: Recipe, desired_slot: str) -> bool:
+        normalized_title = normalize_name(recipe.title)
+        if desired_slot == "breakfast" and any(keyword in normalized_title for keyword in ("sauce", "dip", "dressing", "relish", "spread", "marinade", "condiment")):
+            return False
+        if not any(keyword in normalized_title for keyword in NON_MEAL_TITLE_KEYWORDS):
+            return True
+        if any(keyword in normalized_title for keyword in SUBSTANTIAL_MEAL_KEYWORDS):
+            return True
+        core_ingredient_count = len(self._core_ingredient_names(recipe))
+        return core_ingredient_count >= 5
```

```diff
diff --git a/tests/test_phase6_planning.py b/tests/test_phase6_planning.py
@@
+class MealReasonablenessRecipeProvider(LocalRecipeProvider):
+    ...
@@
+    def test_non_meal_titles_are_filtered_out_of_dinner_candidates(self) -> None:
+        ...
+        self.assertEqual(
+            [recipe.title for recipe in dinner_candidates],
+            ["Black Bean Chili Bowl", "Lemon Chicken Skillet"],
+        )
+
+    def test_dinner_filter_keeps_multiple_valid_meal_candidates(self) -> None:
+        ...
+        self.assertEqual(len(dinner_candidates), 2)
+        self.assertEqual(
+            {recipe.title for recipe in dinner_candidates},
+            {"Lemon Chicken Skillet", "Black Bean Chili Bowl"},
+        )
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_planning.PlanningPhase6Tests.test_non_meal_titles_are_filtered_out_of_dinner_candidates tests.test_phase6_planning.PlanningPhase6Tests.test_dinner_filter_keeps_multiple_valid_meal_candidates tests.test_phase6_planning.PlanningPhase6Tests.test_unknown_calorie_data_fails_with_clear_message tests.test_phase3_app_failure
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.planner import WeeklyMealPlanner; from pantry_pilot.providers import LocalRecipeProvider; planner=WeeklyMealPlanner(recipe_provider=LocalRecipeProvider()); request=PlannerRequest(weekly_budget=80.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',), pricing_mode='mock', daily_calorie_target_min=1600, daily_calorie_target_max=2200, variety_preference='balanced', leftovers_mode='off'); recipes=planner.filter_recipes(request); bad_titles=('Garlic Aioli (Dipping Sauce for French Fries)','Indian Onion Relish','Authentic Mexican Guacamole'); print('BAD_FILTER_RESULTS', [(title, next(planner._is_reasonable_meal_for_slot(recipe, 'dinner') for recipe in recipes if recipe.title==title)) for title in bad_titles]); print('REASONABLE_DINNER_COUNT', len([recipe for recipe in recipes if planner._is_reasonable_meal_for_slot(recipe, 'dinner')]))"
```

### Verification Result

- Targeted tests passed:
  - `Ran 5 tests in 0.001s`
  - `OK`
- Known bad RecipeNLG dinner examples are now rejected:
  - `BAD_FILTER_RESULTS [('Garlic Aioli (Dipping Sauce for French Fries)', False), ('Indian Onion Relish', False), ('Authentic Mexican Guacamole', False)]`
- The dinner candidate pool still remains large on the current full RecipeNLG dataset:
  - `REASONABLE_DINNER_COUNT 21449`
- Recent Phase 3 behavior still held during verification:
  - targeted app failure and unknown-calorie enforcement checks still passed

### Recommended Next Phase

- Proceed to **Phase 5 - Add a supporting nutrition/cost layer only if still needed after Phases 2-4**
- Important carry-forward note:
  - the meal filter fixed the non-meal slot problem, but the current full RecipeNLG dataset still lacks calorie support for honest calorie-constrained planning
- Important carry-forward note:
  - the planner now fails honestly on the current full RecipeNLG dataset because calorie metadata is missing, which is a data-support gap to revisit in Phase 5 if it remains necessary after Phase 4

## Phase 3 - Follow-up for app failure messaging

### Status

PASS

### Root Cause Found

- The planner was already returning the correct specific failure reason.
- The app was masking that reason by catching `PlannerError`, calling `diagnose_plan_failure(...)`, and then showing the generic headline `PantryPilot could not build a full week from the current settings.`
- The specific planner message was only relegated to a small caption, which made the real blocker easy to miss.

### Files Inspected

- `mvp/app.py`
- `pantry_pilot/plan_failures.py`
- `pantry_pilot/planner.py`
- `tests/test_phase3_app_failure.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `mvp/app.py`
- `pantry_pilot/plan_failures.py`
- `tests/test_phase3_app_failure.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/plan_failures.py b/pantry_pilot/plan_failures.py
+GENERIC_PLAN_FAILURE_HEADLINE = "PantryPilot could not build a full week from the current settings."
+
+def build_failure_feedback(planner_error_message: str, likely_causes: list[str]) -> tuple[str, list[str]]:
+    primary_message = planner_error_message.strip() or GENERIC_PLAN_FAILURE_HEADLINE
+    filtered_causes = [
+        cause
+        for cause in likely_causes
+        if cause.strip() and cause.strip() != primary_message and cause.strip() != GENERIC_PLAN_FAILURE_HEADLINE
+    ]
+    return primary_message, filtered_causes
```

```diff
diff --git a/mvp/app.py b/mvp/app.py
@@
+from pantry_pilot.plan_failures import build_failure_feedback
@@
-        headline, likely_causes = diagnose_plan_failure(planner, request)
-        st.error(headline)
-        st.caption(str(exc))
-        with st.container(border=True):
-            st.markdown("**Likely Causes**")
-            for cause in likely_causes:
-                st.write(f"- {cause}")
+        _, likely_causes = diagnose_plan_failure(planner, request)
+        headline, likely_causes = build_failure_feedback(str(exc), likely_causes)
+        st.error(headline)
+        if likely_causes:
+            with st.container(border=True):
+                st.markdown("**Likely Causes**")
+                for cause in likely_causes:
+                    st.write(f"- {cause}")
```

```diff
diff --git a/tests/test_phase3_app_failure.py b/tests/test_phase3_app_failure.py
+class Phase3AppFailureTests(unittest.TestCase):
+    def test_specific_planner_error_becomes_primary_app_message(self) -> None:
+        ...
+
+    def test_generic_fallback_is_used_when_no_specific_error_exists(self) -> None:
+        ...
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase3_app_failure tests.test_phase6_planning.PlanningPhase6Tests.test_unknown_calorie_data_fails_with_clear_message
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.plan_failures import build_failure_feedback; from pantry_pilot.planner import PlannerError, WeeklyMealPlanner; planner=WeeklyMealPlanner(); request=PlannerRequest(weekly_budget=80.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',), pricing_mode='mock', daily_calorie_target_min=1600, daily_calorie_target_max=2200, variety_preference='balanced', leftovers_mode='off'); \
try: \
    planner.create_plan(request); print('APP_MESSAGE', 'unexpected success') \
except PlannerError as exc: \
    headline, causes = build_failure_feedback(str(exc), ['The calorie target range is restrictive enough to block an otherwise feasible plan.']); \
    print('APP_MESSAGE', headline); print('CAUSES', causes)"
```

### Verification Result

- Targeted tests passed:
  - `Ran 3 tests in 0.001s`
  - `OK`
- Reproduced the same weekly planning failure path and confirmed the surfaced app message is now:
  - `No recipes with known calorie estimates are available for dinner, so the calorie target cannot be satisfied.`
- Planner enforcement did not regress:
  - the same planner failure is still raised
  - only the app presentation logic changed

### Recommended Next Phase

- Proceed to **Phase 4 - Filter out non-meals from breakfast/lunch/dinner**

## Phase 2 - Follow-up fix for app/runtime None handling

### Status

PASS

### Root Cause Found

- Phase 2 correctly preserved unknown calories and prep time as `None`, but the Streamlit app still assumed those fields were always numeric.
- The crash at `mvp/app.py` came from direct arithmetic on `meal.recipe.estimated_calories_per_serving * meal.scaled_servings`.
- Nearby app paths had the same unsafe assumption in:
  - weekly calorie summary
  - daily calorie summary and target status
  - meal-level calorie display
  - meal-level prep-time display
  - saved-plan average-calorie caption
  - text and CSV export formatting for unknown calorie and cost values

### Files Inspected

- `mvp/app.py`
- `pantry_pilot/plan_display.py`
- `pantry_pilot/favorites.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase2_providers.py`
- `tests/test_phase5_pricing.py`

### Files Changed

- `mvp/app.py`
- `pantry_pilot/plan_display.py`
- `tests/test_phase2_app_display.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/plan_display.py b/pantry_pilot/plan_display.py
+@dataclass(frozen=True)
+class CalorieSummary:
+    known_total: int
+    unknown_meal_count: int
+    meal_count: int
+
+def summarize_calories(meals: Iterable[PlannedMeal]) -> CalorieSummary:
+    ...
+
+def format_optional_minutes(minutes: int | None) -> str:
+    ...
+
+def format_optional_currency(amount: float | None) -> str:
+    ...
+
+def calorie_status_label(summary: CalorieSummary, minimum: int, maximum: int) -> tuple[str, str]:
+    ...
+
+def build_plan_text_export(...):
+    ...
+
+def build_shopping_list_csv(plan: MealPlan) -> str:
+    ...
```

```diff
diff --git a/mvp/app.py b/mvp/app.py
@@
-weekly_calories = sum(meal.recipe.estimated_calories_per_serving * meal.scaled_servings for meal in plan.meals)
-average_daily_calories = round(weekly_calories / 7)
+weekly_calorie_summary = summarize_calories(plan.meals)
@@
-calorie_metrics[0].metric("Weekly Calories", f"{weekly_calories:,}")
-calorie_metrics[1].metric("Average Per Day", f"{average_daily_calories:,}")
+calorie_metrics[0].metric("Weekly Calories", format_calorie_total_metric(weekly_calorie_summary))
+calorie_metrics[1].metric("Average Per Day", format_average_calorie_metric(weekly_calorie_summary))
@@
-daily_calories = sum(meal.recipe.estimated_calories_per_serving * meal.scaled_servings for meal in day_meals)
-day_status, day_status_help = calorie_status_label(daily_calories, ...)
+daily_calorie_summary = summarize_calories(day_meals)
+day_status, day_status_help = calorie_status_label(daily_calorie_summary, ...)
@@
-prep_col.metric("Prep Time", f"{meal.recipe.prep_time_minutes} min")
+prep_col.metric("Prep Time", format_optional_minutes(meal.recipe.prep_time_minutes))
@@
-calorie_col.metric("Calories", f"{meal.recipe.estimated_calories_per_serving * meal.scaled_servings:,}")
+calorie_col.metric("Calories", "Unknown" if meal_calories is None else f"{meal_calories:,}")
@@
-st.caption(f"Estimated calories per serving: {meal.recipe.estimated_calories_per_serving:,}")
+st.caption("Estimated calories per serving: " + format_optional_calories_per_serving(meal.recipe.estimated_calories_per_serving))
```

```diff
diff --git a/tests/test_phase2_app_display.py b/tests/test_phase2_app_display.py
+def test_calorie_summary_marks_partial_totals_and_unknown_status(self) -> None:
+    ...
+
+def test_export_helpers_render_unknown_values_without_crashing(self) -> None:
+    ...
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase2_app_display tests.test_phase2_providers.Phase2ProviderTests.test_processed_dataset_preserves_unknown_calories_and_prep_time tests.test_phase5_pricing.PricingPhase5Tests.test_unknown_conversion_cost_does_not_show_as_zero
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -c "from pantry_pilot.models import MealPlan, PlannedMeal, PlannerRequest, Recipe, RecipeIngredient, ShoppingListItem; from pantry_pilot.plan_display import build_plan_text_export, build_shopping_list_csv, summarize_calories, format_calorie_total_metric; recipe=Recipe(recipe_id='unknown', title='Unknown Bowl', cuisine='mediterranean', base_servings=2, estimated_calories_per_serving=None, prep_time_minutes=None, meal_types=('dinner',), diet_tags=frozenset({'vegan'}), allergens=frozenset(), ingredients=(RecipeIngredient('rice',1.0,'cup'),), steps=('Cook it.',)); plan=MealPlan(meals=(PlannedMeal(day=1, slot=1, recipe=recipe, scaled_servings=2, incremental_cost=3.25),), shopping_list=(ShoppingListItem(name='apple', quantity=2.5, unit='cup', estimated_packages=0, purchased_quantity=0.0, estimated_cost=None, pricing_source='mock'),), estimated_total_cost=3.25); request=PlannerRequest(weekly_budget=80.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',)); summary=summarize_calories(plan.meals); print('WEEKLY', format_calorie_total_metric(summary)); print('EXPORT_HAS_UNKNOWN', 'Weekly calories: Unknown' in build_plan_text_export(request, plan, '1,600 to 2,200 calories per day')); print('CSV_HAS_UNKNOWN', 'Unknown' in build_shopping_list_csv(plan))"
```

### Verification Result

- Targeted tests passed:
  - `Ran 4 tests in 0.005s`
  - `OK`
- Smoke check passed:
  - `WEEKLY Unknown`
  - `EXPORT_HAS_UNKNOWN True`
  - `CSV_HAS_UNKNOWN True`
- The app-side calorie, prep-time, and unknown-cost formatting path is now render-safe for `None` values.
- Chosen MVP behavior:
  - weekly and saved-plan calorie summaries show known totals only when partial and label them as known/partial
  - daily target status becomes `Unknown` when any meal that day lacks calorie data
  - meal-level unknown prep time, calories, and item costs render as `Unknown`, not fake zeroes

### Recommended Next Phase

- Proceed to **Phase 3 - Make calorie target and weekly budget materially affect planning**

## Phase 5 - Add a supporting nutrition/cost layer only if still needed after Phases 2-4

### Status

PASS

### Root Cause Found

- After Phases 2-4, the planner was still failing honestly on the full RecipeNLG dataset because most rows had no calorie metadata at all.
- The existing ingredient catalog contained canonical ingredient names and units, but it did not yet carry calorie reference values.
- The mock grocery provider still lacked several high-frequency dinner ingredients, and common item-to-cup or item-to-lb conversions were still causing otherwise known ingredients to become unpriced.
- That meant calorie targets and weekly budgets could be enforced correctly in principle, but the current offline data support layer was too thin to satisfy those constraints on the real RecipeNLG corpus.

### Files Inspected

- `pantry_pilot/ingredient_catalog.py`
- `pantry_pilot/recipe_estimation.py`
- `pantry_pilot/providers.py`
- `pantry_pilot/planner.py`
- `tests/test_phase2_providers.py`
- `tests/test_phase5_pricing.py`

### Files Changed

- `pantry_pilot/ingredient_catalog.py`
- `pantry_pilot/recipe_estimation.py`
- `pantry_pilot/providers.py`
- `pantry_pilot/planner.py`
- `tests/test_phase2_providers.py`
- `tests/test_phase5_pricing.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/ingredient_catalog.py b/pantry_pilot/ingredient_catalog.py
@@
+INGREDIENT_UNIT_CONVERSION_FACTORS = {
+    ("apple", "item", "cup"): 1.5,
+    ("chicken breast", "item", "lb"): 0.5,
+    ("garlic", "clove", "tsp"): 1.0,
+    ...
+}
+
+INGREDIENT_CALORIE_REFERENCES = {
+    "rice": (206.0, "cup"),
+    "black beans": (227.0, "can"),
+    "chicken breast": (748.0, "lb"),
+    ...
+}
+
+def ingredient_calorie_reference(value: str) -> tuple[float, str] | None:
+    ...
+
+def convert_ingredient_unit_quantity(...):
+    ...
```

```diff
diff --git a/pantry_pilot/recipe_estimation.py b/pantry_pilot/recipe_estimation.py
new file mode 100644
@@
+def estimate_calories_per_serving(
+    ingredients: tuple[RecipeIngredient, ...],
+    servings: int,
+) -> int | None:
+    ...
```

```diff
diff --git a/pantry_pilot/providers.py b/pantry_pilot/providers.py
@@
+from pantry_pilot.recipe_estimation import estimate_calories_per_serving
@@
+    if calories_per_serving is None:
+        calories_per_serving = estimate_calories_per_serving(ingredients, servings)
@@
+            "chicken broth": GroceryProduct(...),
+            "lemon juice": GroceryProduct(...),
+            "mayonnaise": GroceryProduct(...),
+            "walnuts": GroceryProduct(...),
+            ...
```

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
+from pantry_pilot.ingredient_catalog import convert_ingredient_unit_quantity
@@
-        purchasable_quantity = self._convert_to_purchase_unit(required_quantity, required_unit, product.unit)
+        purchasable_quantity = self._convert_to_purchase_unit(ingredient_name, required_quantity, required_unit, product.unit)
@@
-        return convert_unit_quantity(quantity, normalized_recipe_unit, normalized_product_unit)
+        return convert_ingredient_unit_quantity(ingredient_name, quantity, normalized_recipe_unit, normalized_product_unit)
```

```diff
diff --git a/tests/test_phase2_providers.py b/tests/test_phase2_providers.py
@@
+    def test_processed_dataset_estimates_calories_from_supported_ingredients(self) -> None:
+        ...
+        self.assertEqual(recipe.estimated_calories_per_serving, 320)
```

```diff
diff --git a/tests/test_phase5_pricing.py b/tests/test_phase5_pricing.py
@@
+    def test_common_item_to_cup_gap_now_uses_estimated_purchase_cost(self) -> None:
+        ...
+        self.assertEqual(apple.estimated_cost, 1.5)
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase2_providers.Phase2ProviderTests.test_processed_dataset_preserves_unknown_calories_and_prep_time_when_no_support_layer_exists tests.test_phase2_providers.Phase2ProviderTests.test_processed_dataset_estimates_calories_from_supported_ingredients tests.test_phase5_pricing.PricingPhase5Tests.test_unknown_conversion_cost_does_not_show_as_zero tests.test_phase5_pricing.PricingPhase5Tests.test_common_item_to_cup_gap_now_uses_estimated_purchase_cost tests.test_phase6_planning.PlanningPhase6Tests.test_unknown_calorie_data_fails_with_clear_message tests.test_phase6_planning.PlanningPhase6Tests.test_unknown_price_data_fails_with_clear_message
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.planner import WeeklyMealPlanner; from pantry_pilot.providers import LocalRecipeProvider, DEFAULT_PROCESSED_RECIPES_PATH; provider=LocalRecipeProvider(); recipes=provider.list_recipes(); planner=WeeklyMealPlanner(recipe_provider=provider); request=PlannerRequest(weekly_budget=140.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',), pricing_mode='mock', daily_calorie_target_min=800, daily_calorie_target_max=1200, variety_preference='balanced', leftovers_mode='off'); plan=planner.create_plan(request); print('DATASET', DEFAULT_PROCESSED_RECIPES_PATH); print('TOTAL_RECIPES', len(recipes)); print('KNOWN_CALORIES', sum(recipe.estimated_calories_per_serving is not None for recipe in recipes)); print('PLAN_TOTAL', plan.estimated_total_cost); print('PLAN_DAILY_CALORIES', [meal.recipe.estimated_calories_per_serving * meal.scaled_servings for meal in plan.meals]); print('SHOPPING_UNKNOWN_COSTS', sum(item.estimated_cost is None for item in plan.shopping_list))"
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.planner import WeeklyMealPlanner; from pantry_pilot.providers import LocalRecipeProvider; provider=LocalRecipeProvider(); planner=WeeklyMealPlanner(recipe_provider=provider); request=PlannerRequest(weekly_budget=140.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',), pricing_mode='mock', daily_calorie_target_min=800, daily_calorie_target_max=1200, variety_preference='balanced', leftovers_mode='off'); dinner_candidates=planner._recipes_for_slot(planner.filter_recipes(request), request, 1); print('DINNER_CANDIDATES', len(dinner_candidates)); print('KNOWN_CALORIE_DINNERS', sum(recipe.estimated_calories_per_serving is not None for recipe in dinner_candidates)); print('FULLY_PRICED_DINNERS', sum(planner._recipe_cost_is_known(recipe, request, frozenset()) for recipe in dinner_candidates)); print('KNOWN_AND_FULLY_PRICED_DINNERS', sum(recipe.estimated_calories_per_serving is not None and planner._recipe_cost_is_known(recipe, request, frozenset()) for recipe in dinner_candidates))"
```

### Verification Result

- Targeted support-layer tests passed:
  - `Ran 6 tests in 0.008s`
  - `OK`
- Full RecipeNLG load now recovers calorie support for most recipes:
  - `TOTAL_RECIPES 23021`
  - `KNOWN_CALORIES 21275`
- Dinner candidate support is now materially better:
  - `DINNER_CANDIDATES 17919`
  - `KNOWN_CALORIE_DINNERS 16483`
  - `FULLY_PRICED_DINNERS 16055`
  - `KNOWN_AND_FULLY_PRICED_DINNERS 15877`
- A full RecipeNLG weekly dinner plan now builds under calorie and budget constraints without unknown shopping-list costs:
  - `PLAN_RESULT PASS`
  - `PLAN_TOTAL 17.5`
  - `SHOPPING_UNKNOWN_COSTS 0`

### Recommended Next Phase

- Proceed to **Phase 6 - Add regression tests and fast demo checks**
- Carry-forward note:
  - calorie and price support are now materially better on the real RecipeNLG corpus, but broader title-based non-meal filtering still deserves continued regression coverage because some dessert or condiment-style edge cases can still survive outside the originally reproduced examples

## Phase 6 - Add regression tests and fast demo checks

### Status

PASS

### Root Cause Found

- The planner fixes were spread across multiple earlier phase-specific tests, but there was no compact regression suite that could verify the whole RecipeNLG planner path quickly.
- The Streamlit app still depended on top-level runtime code in `mvp/app.py`, which made a direct app smoke test awkward without importing the whole UI module.
- A small shared app-runtime helper was enough to make the current app plan path testable without adding new features or rerunning imports.

### Files Inspected

- `mvp/app.py`
- `tests/test_phase6_planning.py`
- `tests/test_phase2_providers.py`
- `tests/test_phase5_pricing.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `pantry_pilot/app_runtime.py`
- `mvp/app.py`
- `tests/test_phase6_regressions.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/app_runtime.py b/pantry_pilot/app_runtime.py
new file mode 100644
@@
+@dataclass(frozen=True)
+class AppPlanSnapshot:
+    ...
+
+def format_calorie_target(minimum: int, maximum: int) -> str:
+    ...
+
+def build_planner_and_context(request: PlannerRequest) -> tuple[WeeklyMealPlanner, PricingContext]:
+    ...
+
+def build_plan_snapshot(request: PlannerRequest) -> AppPlanSnapshot:
+    ...
```

```diff
diff --git a/mvp/app.py b/mvp/app.py
@@
+from pantry_pilot.app_runtime import build_planner_and_context, format_calorie_target
@@
-from pantry_pilot.providers import build_pricing_context, discover_kroger_locations, format_location_label
+from pantry_pilot.providers import discover_kroger_locations, format_location_label
@@
-def build_planner_and_context(request: PlannerRequest) -> tuple[WeeklyMealPlanner, object]:
-    ...
-
-def format_calorie_target(minimum: int, maximum: int) -> str:
-    ...
```

```diff
diff --git a/tests/test_phase6_regressions.py b/tests/test_phase6_regressions.py
new file mode 100644
@@
+class PlannerRegressionPhase6Tests(unittest.TestCase):
+    @classmethod
+    def setUpClass(cls) -> None:
+        cls.real_request = PlannerRequest(...)
+        cls.real_snapshot = build_plan_snapshot(cls.real_request)
+
+    def test_default_path_points_to_full_recipenlg_dataset(self) -> None:
+        ...
+
+    def test_unsupported_unknown_metadata_stays_unknown_not_zero(self) -> None:
+        ...
+
+    def test_calorie_target_materially_changes_output(self) -> None:
+        ...
+
+    def test_weekly_budget_materially_changes_output(self) -> None:
+        ...
+
+    def test_known_bad_real_titles_are_excluded_from_dinner_candidates(self) -> None:
+        ...
+
+    def test_real_dataset_constrained_plan_succeeds_with_supported_costs(self) -> None:
+        ...
+
+    def test_app_runtime_smoke_builds_plan_exports_without_crashing(self) -> None:
+        ...
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -c "from pantry_pilot.app_runtime import build_plan_snapshot; from pantry_pilot.models import PlannerRequest; snapshot = build_plan_snapshot(PlannerRequest(weekly_budget=140.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',), pricing_mode='mock', daily_calorie_target_min=800, daily_calorie_target_max=1200, variety_preference='balanced', leftovers_mode='off')); print('SMOKE_PRICING', snapshot.pricing_context.pricing_source); print('SMOKE_MEAL_COUNT', len(snapshot.plan.meals)); print('SMOKE_TOTAL_COST', snapshot.plan.estimated_total_cost); print('SMOKE_FIRST_MEAL', snapshot.plan.meals[0].recipe.title); print('SMOKE_EXPORT_HAS_WEEKLY', 'Weekly calories:' in snapshot.export_text); print('SMOKE_CSV_HEADER', snapshot.shopping_list_csv.splitlines()[0]); print('SMOKE_UNKNOWN_COSTS', sum(item.estimated_cost is None for item in snapshot.plan.shopping_list))"
```

### Verification Result

- Fast regression suite passed:
  - `Ran 8 tests in 22.475s`
  - `OK`
- Standalone app-runtime smoke check passed:
  - `SMOKE_PRICING mock`
  - `SMOKE_MEAL_COUNT 7`
  - `SMOKE_TOTAL_COST 17.5`
  - `SMOKE_FIRST_MEAL Mash Potato Candy`
  - `SMOKE_EXPORT_HAS_WEEKLY True`
  - `SMOKE_CSV_HEADER Ingredient,Amount Needed,Amount Being Bought,Package Count,Estimated Cost,Price Source`
  - `SMOKE_UNKNOWN_COSTS 0`
- Future verification of the planner fixes now uses a single small unittest module plus one optional smoke command. No long dataset re-import rerun is needed.

### Recommended Next Phase

- Proceed to **Phase 7 - MAE301 MVP compliance audit**

## Phase 7 - MAE301 MVP compliance audit

### Status

PASS

### Root Cause Found

- The core MVP deliverables were present, but several docs still described an earlier milestone state where the planner was not wired to `mvp/data/` and the app still used the sample dataset by default.
- The repo already contained the required MVP artifacts, but the course-facing documentation needed a small accuracy pass so reproducibility and evaluation evidence matched the current RecipeNLG-based system.
- No planner or safety code change was needed in this phase. The gap was documentation drift.

### Files Inspected

- `README.md`
- `mvp/README.md`
- `mvp/report.md`
- `mvp/data/README.md`
- `mvp/data/raw/README.md`
- `mvp/data/processed/README.md`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `README.md`
- `mvp/report.md`
- `mvp/data/README.md`
- `mvp/data/raw/README.md`
- `mvp/data/processed/README.md`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/README.md b/README.md
@@
-## Milestone 1 dataset scaffold
-...
-The Streamlit app still uses the existing sample recipe provider in this milestone.
+## Current MVP dataset
+...
+The app falls back to the built-in sample dataset only if the processed dataset is missing or invalid.
+...
+## MVP reproducibility
+...
```

```diff
diff --git a/mvp/data/README.md b/mvp/data/README.md
@@
-The planner is not wired to these directories yet in Milestone 1.
+Current MVP runtime behavior:
+- the app defaults to `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
+- the app falls back to the built-in sample dataset only if the processed dataset fails to load
```

```diff
diff --git a/mvp/data/raw/README.md b/mvp/data/raw/README.md
@@
+Current primary offline source:
+- RecipeNLG CSV: `mvp/data/raw/recipenlg/RecipeNLG_dataset.csv`
```

```diff
diff --git a/mvp/data/processed/README.md b/mvp/data/processed/README.md
@@
+Current main offline dataset artifacts:
+- `recipenlg-full-20260416T0625Z.json`
+- `recipenlg-full-20260416T0625Z.stats.json`
+- `recipenlg-full-20260416T0625Z.checkpoint.json`
+...
```

```diff
diff --git a/mvp/report.md b/mvp/report.md
@@
+Current reproducible evidence in the repo:
+- full RecipeNLG import artifacts
+- planner fix log
+- fast regression suite
+...
+Suggested instructor verification commands:
+...
+## MAE301 Deliverable Check
+...
+Remaining gap list after this audit:
+- no major MVP deliverable is missing
```

### Verification Command(s)

```powershell
rg -n "sample recipe provider in this milestone|planner is not wired|Current MVP dataset|RecipeNLG CSV|MAE301 Deliverable Check|test_phase6_regressions" README.md mvp docs
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions
```

### Verification Result

- Documentation audit confirmed the stale milestone wording was removed and replaced with the current MVP state.
- The repo now clearly documents:
  - `/mvp/` app code
  - `/mvp/README.md`
  - `/mvp/report.md`
  - data source and preprocessing paths
  - reproducible evaluation evidence
  - limitations, risks, and next steps
- Fast regression suite still passed after the documentation-only patch.
- No major MAE301 MVP deliverable is currently missing from the repo.

### Recommended Next Phase

- No automatic next phase.
- If you want to keep polishing submission readiness, the remaining work is packaging cleanup:
  - decide whether to prune or ignore old generated processed artifacts before submission
  - optionally add a stable alias for the main RecipeNLG dataset filename

## Phase 8 - Repetition and variety control

### Status

PASS

### Root Cause Found

- The planner already applied repeat penalties, but two user-visible repetition issues remained:
  - repeated identical requests always returned the same weekly plan because ties were resolved from a stable sorted candidate list
  - `leftovers_mode="off"` still allowed exact repeats inside a week too early because the normal weekly cap for balanced variety was still `2`
- This was not a calorie, budget, allergen, or meal-reasonableness regression. It was a selection-order problem in `pantry_pilot/planner.py`.

### Files Inspected

- `pantry_pilot/planner.py`
- `tests/test_phase6_planning.py`
- `tests/test_phase6_regressions.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `pantry_pilot/planner.py`
- `tests/test_phase6_planning.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
+import hashlib
@@
+class ChoiceCandidate:
+    ...
@@
+    _request_cycle_offsets: dict[str, int] = {}
@@
+        request_cycle_offset = self._next_request_cycle_offset(request)
@@
+        ranked_choices.sort(key=lambda candidate: candidate.sort_key)
+        selected_choice = self._select_diverse_choice(...)
@@
+        return VarietyProfile(
+            same_recipe_weekly_cap=1,
+            ...
+        )
+    @classmethod
+    def reset_request_cycle_offsets(cls) -> None:
+        ...
```

```diff
diff --git a/tests/test_phase6_planning.py b/tests/test_phase6_planning.py
@@
+class ExpandedVarietyRecipeProvider(LocalRecipeProvider):
+    ...
@@
+    def setUp(self) -> None:
+        WeeklyMealPlanner.reset_request_cycle_offsets()
+    def test_leftovers_off_avoids_duplicate_meals_when_unique_options_exist(self) -> None:
+        ...
+    def test_repeated_identical_requests_rotate_among_near_equal_weekly_plans(self) -> None:
+        ...
+    def test_real_dataset_budget_and_calorie_constrained_plan_still_succeeds_with_variety_controls(self) -> None:
+        ...
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_planning.PlanningPhase6Tests.test_leftovers_off_avoids_duplicate_meals_when_unique_options_exist tests.test_phase6_planning.PlanningPhase6Tests.test_repeated_identical_requests_rotate_among_near_equal_weekly_plans tests.test_phase6_planning.PlanningPhase6Tests.test_real_dataset_budget_and_calorie_constrained_plan_still_succeeds_with_variety_controls tests.test_phase6_regressions
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.planner import WeeklyMealPlanner; from pantry_pilot.providers import LocalRecipeProvider; WeeklyMealPlanner.reset_request_cycle_offsets(); planner=WeeklyMealPlanner(recipe_provider=LocalRecipeProvider()); request=PlannerRequest(weekly_budget=140.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',), pricing_mode='mock', daily_calorie_target_min=800, daily_calorie_target_max=1200, variety_preference='balanced', leftovers_mode='off'); plan1=planner.create_plan(request); plan2=planner.create_plan(request); print('PLAN1', [meal.recipe.title for meal in plan1.meals]); print('PLAN2', [meal.recipe.title for meal in plan2.meals]); print('PLAN1_DUPES', len(plan1.meals) - len({meal.recipe.title for meal in plan1.meals})); print('PLAN2_DUPES', len(plan2.meals) - len({meal.recipe.title for meal in plan2.meals})); print('PLAN1_COST', plan1.estimated_total_cost); print('PLAN2_COST', plan2.estimated_total_cost)"
```

### Verification Result

- Repeated identical requests now rotate among near-equal valid plans instead of always collapsing to the exact same title sequence.
- When `leftovers_mode="off"` and enough unique candidates exist, duplicate recipes disappear within the week.
- Budget and calorie constrained planning still succeeds on the real RecipeNLG dataset.
- The fast regression suite still passes after the variety patch.

### Recommended Next Step

- No automatic next phase.
- If you keep polishing planner quality, the next likely improvement is more nuanced dessert-or-snack suppression for edge-case RecipeNLG titles that are still meal-shaped enough to survive the current heuristics.

## Phase 9 - Repeat-cap diagnosis, cost semantics, and meal realism triage

### Status

PASS

### Root Cause Found

- The repeat-cap warning was partly caused by a planner bug, not just true candidate scarcity:
  - the planner could choose a repeat because of a soft per-slot budget guardrail even when a unique recipe still fit the overall weekly budget
  - lunch selection was too literal for RecipeNLG because only a handful of recipes were tagged as lunch, even though many dinner-style mains were reasonable lunch candidates
- Meal cost semantics were blurred in the app:
  - `incremental_cost` is package-based added shopping cost
  - the UI was labeling that as meal cost instead of a consumed ingredient estimate
- Meal realism still had obvious title leaks for lunch and dinner:
  - desserts, drinks, candy, jams, and plain breads could still be treated as full meals
  - condiment-style titles with many ingredients could still slip through

### Files Inspected

- `pantry_pilot/planner.py`
- `pantry_pilot/models.py`
- `pantry_pilot/favorites.py`
- `pantry_pilot/plan_display.py`
- `mvp/app.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase6_planning.py`
- `tests/test_phase6_regressions.py`
- `tests/test_phase7_favorites.py`

### Files Changed

- `pantry_pilot/planner.py`
- `pantry_pilot/models.py`
- `pantry_pilot/favorites.py`
- `pantry_pilot/plan_display.py`
- `mvp/app.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase6_planning.py`
- `tests/test_phase7_favorites.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
+NON_MEAL_LUNCH_DINNER_KEYWORDS = frozenset(...)
+HARD_NON_MEAL_TITLE_KEYWORDS = frozenset(...)
+class SlotSelectionDiagnostics: ...
+class PlanSelectionDiagnostics: ...
@@
-        if preferred_choice is not None:
-            if (...):
-                return preferred_choice[0], preferred_choice[1], False
+        if preferred_choice is not None:
+            return preferred_choice[0], preferred_choice[1], False
@@
+        if desired == "lunch":
+            return tuple(
+                recipe for recipe in candidates
+                if "lunch" in recipe.meal_types or "dinner" in recipe.meal_types
+            )
@@
+    def diagnose_request_support(self, request: PlannerRequest) -> PlanSelectionDiagnostics:
+        ...
+    def _estimate_recipe_consumed_cost(...):
+        ...
+    def _consumed_requirement_cost(...):
+        ...
```

```diff
diff --git a/pantry_pilot/models.py b/pantry_pilot/models.py
@@
 class PlannedMeal:
     ...
     incremental_cost: float
+    consumed_cost: float | None = None
```

```diff
diff --git a/mvp/app.py b/mvp/app.py
@@
-                    cost_col.metric("Meal Cost", format_optional_currency(meal.incremental_cost))
+                    consumed_col.metric("Consumed Cost", format_optional_currency(meal.consumed_cost))
+                    shopping_col.metric("Added Shopping", format_optional_currency(meal.incremental_cost))
+                    st.caption("Consumed cost estimates ingredient usage. Added shopping reflects whole-package purchases added to the weekly cart.")
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase2_app_display tests.test_phase7_favorites tests.test_phase6_planning.PlanningPhase6Tests.test_dessert_and_drink_titles_are_filtered_out_of_dinner_candidates tests.test_phase6_planning.PlanningPhase6Tests.test_meal_consumed_cost_is_distinct_from_added_shopping_cost tests.test_phase6_planning.PlanningPhase6Tests.test_repeat_warning_is_not_triggered_when_unique_under_budget_options_exist
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -c "from pantry_pilot.models import PlannerRequest; from pantry_pilot.planner import WeeklyMealPlanner; from pantry_pilot.providers import LocalRecipeProvider; planner=WeeklyMealPlanner(recipe_provider=LocalRecipeProvider()); request=PlannerRequest(weekly_budget=300.0, servings=2, cuisine_preferences=('mediterranean','mexican','american'), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=('olive oil','cinnamon'), max_prep_time_minutes=35, meals_per_day=2, meal_structure=('lunch','dinner'), pricing_mode='mock', daily_calorie_target_min=1600, daily_calorie_target_max=2200, variety_preference='balanced', leftovers_mode='off'); d=planner.diagnose_request_support(request); plan=planner.create_plan(request); print('FORCED_REPEAT_SLOTS', d.forced_repeat_slots); print('TRUTHFUL', d.repeat_message_truthful); print('TOP_REJECTIONS', d.top_rejection_reasons[:10]); print('PLAN', [meal.recipe.title for meal in plan.meals])"
```

### Verification Result

- Targeted triage tests passed:
  - `Ran 8 tests in 5.842s`
  - `OK`
- Fast regression suite still passed:
  - `Ran 8 tests in 22.986s`
  - `OK`
- Real repeat-cap request after the fix:
  - `FORCED_REPEAT_SLOTS 0`
  - `TRUTHFUL True`
  - `TOP_REJECTIONS (('unknown_calories', 168), ('repeat_cap', 91), ('unusable_price', 14))`
  - repeat-cap note no longer appears for the reproduced `$300` lunch+dinner request
- Real dinner-only plan after the meal-realism triage no longer includes the earlier dessert/drink/jam titles such as `Mash Potato Candy`, `Thai Limeade`, `Italian Water Ice - Lemon`, or `Tomato Jam`
- Cost semantics example:
  - package-based added shopping for a pancake breakfast: `$8.00`
  - consumed ingredient cost for the same meal: `$2.00`

### Recommended Next Step

- No automatic next phase.
- If calorie support becomes the next blocker again, the next data-layer upgrade should be a USDA FoodData Central-backed ingredient mapping, not a new recipe corpus.
- If price support becomes the next blocker again, the next pricing-layer upgrade should be a curated per-unit pantry catalog, not a live pricing system.

## Phase 10 - Pantry carryover and meal-role planning

### Status

PASS

### Root Cause Found

- PantryPilot still treated each week as a fresh shopping session, so whole-package leftovers never reduced later weekly added-shopping cost.
- The planner still treated lunch and dinner as a single undifferentiated role, so it could not require a main dish and only add sides opportunistically.
- Cuisine preferences were still acting as a hard pool filter in the planner, which was needlessly shrinking candidate coverage when RecipeNLG cuisine tags were sparse.

### Files Inspected

- `pantry_pilot/models.py`
- `pantry_pilot/planner.py`
- `pantry_pilot/pantry_carryover.py`
- `pantry_pilot/app_runtime.py`
- `pantry_pilot/plan_display.py`
- `pantry_pilot/favorites.py`
- `mvp/app.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase6_planning.py`
- `tests/test_phase6_regressions.py`
- `tests/test_phase7_favorites.py`
- `tests/test_phase10_pantry_roles.py`

### Files Changed

- `pantry_pilot/models.py`
- `pantry_pilot/planner.py`
- `pantry_pilot/pantry_carryover.py`
- `pantry_pilot/app_runtime.py`
- `pantry_pilot/plan_display.py`
- `pantry_pilot/favorites.py`
- `mvp/app.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase6_planning.py`
- `tests/test_phase6_regressions.py`
- `tests/test_phase10_pantry_roles.py`
- `docs/recipe_planner_fix_plan.md`

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase10_pantry_roles tests.test_phase2_app_display tests.test_phase7_favorites
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions tests.test_phase10_pantry_roles
```

```powershell
@'
... pantry carryover + main/side smoke check ...
'@ | C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -
```

### Verification Result

- New pantry carryover and meal-role tests passed:
  - `Ran 11 tests in 28.176s`
  - `OK`
- Fast regression suite plus the new phase tests passed:
  - `Ran 14 tests in 124.454s`
  - `OK`
- Reproducible carryover smoke check:
  - `PLAN1_COST 20.0`
  - `PLAN1_LEFTOVER 4.0`
  - `PLAN2_COST 10.0`
  - `PLAN2_CARRYOVER_USED 4.0`
  - `PANTRY_AFTER_RESET ()`
- Reproducible main-plus-side smoke check:
  - `DAYS_WITH_SIDE {2: [('Stuffed Peppers', 'main'), ('Roasted Potatoes', 'side')], 5: [('Chicken Skillet', 'main'), ('Herb Beans', 'side')], 6: [('Bean Rice Bowl', 'main'), ('Lemon Rice', 'side')], 7: [('Herby Pasta Plate', 'main'), ('Broccoli Salad', 'side')]}`
- Dessert, beverage, and condiment titles did not appear as main lunch/dinner meals in the targeted role tests.

### Recommended Next Step

- No automatic next phase.
- The highest-value follow-up is a more deliberate meal-balance pass for residual weak mains and side-pairing quality, now that pantry carryover and role separation are in place.

## Phase A - Ingredient Nutrition Integration

### Status

PASS

### Root Cause Found

- PantryPilot already had a calorie-only ingredient estimator, but it did not expose a reusable ingredient-level nutrition model for protein, carbs, and fat.
- The mapping between PantryPilot ingredient names and nutrition support was implicit inside calorie references, which made debugging support gaps harder.
- Recipe-level nutrition remained mostly unavailable because there was no explicit per-ingredient nutrition record layer and no per-recipe nutrition object to carry forward into later planner phases.

### Files Inspected

- `pantry_pilot/models.py`
- `pantry_pilot/providers.py`
- `pantry_pilot/ingredient_catalog.py`
- `pantry_pilot/recipe_estimation.py`
- `pantry_pilot/sample_data.py`
- `pantry_pilot/favorites.py`
- `tests/test_phase2_providers.py`
- `tests/test_phase6_regressions.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `pantry_pilot/models.py`
- `pantry_pilot/nutrition.py`
- `pantry_pilot/recipe_estimation.py`
- `pantry_pilot/providers.py`
- `pantry_pilot/sample_data.py`
- `pantry_pilot/favorites.py`
- `tests/test_phase11_nutrition.py`
- `docs/recipe_planner_fix_plan.md`

### Nutrition Mapping Approach

- Added a new local offline nutrition module at `pantry_pilot/nutrition.py`.
- Defined explicit `IngredientNutritionRecord` entries with:
  - reference unit
  - calories
  - protein grams
  - carb grams
  - fat grams
- Added an explicit `INGREDIENT_TO_NUTRITION_KEY` mapping from PantryPilot canonical ingredient names to those nutrition records.
- Kept mapping debuggable by returning detailed per-ingredient contribution records from `estimate_recipe_nutrition(...)`.
- Preserved honest unknowns:
  - full recipe nutrition is `None` when any ingredient lacks a nutrition mapping or a required unit conversion
  - calorie fallback still uses the older calorie-only support path where available, so this phase improves macro support without regressing existing calorie coverage

### Exact Diff

```diff
diff --git a/pantry_pilot/models.py b/pantry_pilot/models.py
@@
+@dataclass(frozen=True)
+class NutritionEstimate:
+    calories: int
+    protein_grams: float
+    carbs_grams: float
+    fat_grams: float
@@
+    estimated_nutrition_per_serving: NutritionEstimate | None = None
```

```diff
diff --git a/pantry_pilot/nutrition.py b/pantry_pilot/nutrition.py
@@
+@dataclass(frozen=True)
+class IngredientNutritionRecord:
+    key: str
+    reference_unit: str
+    calories: float
+    protein_grams: float
+    carbs_grams: float
+    fat_grams: float
+    source: str = "local-offline"
+...
+INGREDIENT_TO_NUTRITION_KEY = {
+    "apple": "apple",
+    "avocado": "avocado",
+    ...
+}
+...
+def lookup_ingredient_nutrition(value: str) -> IngredientNutritionRecord | None:
+    ...
```

```diff
diff --git a/pantry_pilot/recipe_estimation.py b/pantry_pilot/recipe_estimation.py
@@
+@dataclass(frozen=True)
+class IngredientNutritionContribution:
+    ...
+
+@dataclass(frozen=True)
+class RecipeNutritionComputation:
+    ...
+
+def estimate_recipe_nutrition(
+    ingredients: tuple[RecipeIngredient, ...],
+    servings: int,
+) -> RecipeNutritionComputation:
+    ...
+
 def estimate_calories_per_serving(
     ingredients: tuple[RecipeIngredient, ...],
     servings: int,
 ) -> int | None:
+    nutrition = estimate_recipe_nutrition(ingredients, servings)
+    if nutrition.per_serving is not None:
+        return nutrition.per_serving.calories
     ...
```

```diff
diff --git a/pantry_pilot/providers.py b/pantry_pilot/providers.py
@@
-from pantry_pilot.recipe_estimation import estimate_calories_per_serving
+from pantry_pilot.recipe_estimation import estimate_calories_per_serving, estimate_recipe_nutrition
@@
+    nutrition_per_serving = estimate_recipe_nutrition(ingredients, servings).per_serving
     if calories_per_serving is None:
         calories_per_serving = estimate_calories_per_serving(ingredients, servings)
@@
+        estimated_nutrition_per_serving=nutrition_per_serving,
```

```diff
diff --git a/pantry_pilot/sample_data.py b/pantry_pilot/sample_data.py
@@
+from pantry_pilot.recipe_estimation import estimate_recipe_nutrition
@@
+    base_servings = int(record["base_servings"])
     return Recipe(
         ...
-        base_servings=int(record["base_servings"]),
+        base_servings=base_servings,
         ...
+        estimated_nutrition_per_serving=estimate_recipe_nutrition(ingredients, base_servings).per_serving,
     )
```

```diff
diff --git a/pantry_pilot/favorites.py b/pantry_pilot/favorites.py
@@
-from pantry_pilot.models import MealPlan, PlannedMeal, PlannerRequest, Recipe, RecipeIngredient, ShoppingListItem
+from pantry_pilot.models import MealPlan, NutritionEstimate, PlannedMeal, PlannerRequest, Recipe, RecipeIngredient, ShoppingListItem
@@
+            "estimated_nutrition_per_serving": (
+                None
+                if recipe.estimated_nutrition_per_serving is None
+                else asdict(recipe.estimated_nutrition_per_serving)
+            ),
@@
+        nutrition = recipe_data.get("estimated_nutrition_per_serving")
+        recipe_data["estimated_nutrition_per_serving"] = (
+            None if nutrition is None else NutritionEstimate(**nutrition)
+        )
```

```diff
diff --git a/tests/test_phase11_nutrition.py b/tests/test_phase11_nutrition.py
@@
+class NutritionPhase11Tests(unittest.TestCase):
+    def test_supported_ingredients_produce_nutrition_estimates(self) -> None:
+        ...
+
+    def test_unsupported_ingredients_stay_unknown(self) -> None:
+        ...
+
+    def test_real_recipe_example_gets_ingredient_level_nutrition(self) -> None:
+        ...
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase11_nutrition
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
@'
import json
from pathlib import Path
from pantry_pilot.providers import LocalRecipeProvider, DEFAULT_PROCESSED_RECIPES_PATH

path = Path(DEFAULT_PROCESSED_RECIPES_PATH)
payload = json.loads(path.read_text(encoding="utf-8"))
rows = payload["recipes"]
metadata_known_calories = sum((row.get("calories") or {}).get("calories_per_serving") is not None for row in rows)
recipes = LocalRecipeProvider().list_recipes()
after_known_calories = sum(recipe.estimated_calories_per_serving is not None for recipe in recipes)
after_known_nutrition = sum(recipe.estimated_nutrition_per_serving is not None for recipe in recipes)
unknown_both = [recipe for recipe in recipes if recipe.estimated_calories_per_serving is None and recipe.estimated_nutrition_per_serving is None]
print("BEFORE_METADATA_KNOWN_CALORIES", metadata_known_calories)
print("AFTER_KNOWN_CALORIES", after_known_calories)
print("AFTER_KNOWN_NUTRITION", after_known_nutrition)
print("HONEST_UNKNOWN_COUNT", len(unknown_both))
'@ | C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -
```

```powershell
@'
from pantry_pilot.providers import LocalRecipeProvider
from pantry_pilot.recipe_estimation import estimate_recipe_nutrition

recipe = next(recipe for recipe in LocalRecipeProvider().list_recipes() if recipe.title == "Authentic Mexican Guacamole")
computation = estimate_recipe_nutrition(recipe.ingredients, recipe.base_servings)
print("REAL_RECIPE_NUTRITION_PER_SERVING", recipe.estimated_nutrition_per_serving)
for contribution in computation.contributions:
    print("BREAKDOWN", contribution.ingredient_name, contribution.converted_quantity, contribution.reference_unit, contribution.nutrition, contribution.issue)
'@ | C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -
```

### Before/After Behavior

- Recipe nutrition coverage before vs after:
  - `BEFORE_METADATA_KNOWN_CALORIES 0`
  - `AFTER_KNOWN_CALORIES 21459`
  - `AFTER_KNOWN_NUTRITION 10289`
- Real RecipeNLG ingredient breakdown example:
  - `Authentic Mexican Guacamole`
  - per serving: `NutritionEstimate(calories=125, protein_grams=1.7, carbs_grams=7.9, fat_grams=11.0)`
  - ingredient breakdown:
    - `avocado -> 2.0 item -> NutritionEstimate(calories=480, protein_grams=6.0, carbs_grams=25.6, fat_grams=44.0)`
    - `onion -> 0.062 item -> NutritionEstimate(calories=3, protein_grams=0.1, carbs_grams=0.6, fat_grams=0.0)`
    - `cilantro -> 2.0 tbsp -> NutritionEstimate(calories=2, protein_grams=0.2, carbs_grams=0.2, fat_grams=0.0)`
    - `lemon juice -> 4.0 tbsp -> NutritionEstimate(calories=16, protein_grams=0.4, carbs_grams=5.2, fat_grams=0.0)`
- Honest unknown proof:
  - `HONEST_UNKNOWN_COUNT 1562`
  - real example still unknown: `"Guacamole Dip"`
  - `UNKNOWN_MISSING ('sour cream',)`
  - `UNKNOWN_CALORIES None`
  - `UNKNOWN_NUTRITION None`
- Tests:
  - targeted nutrition suite passed:
    - `Ran 3 tests in 0.015s`
    - `OK`
  - fast regression suite passed:
    - `Ran 8 tests in 67.342s`
    - `OK`

### Readiness For Phase B

- Ready for Phase B.
- This phase now provides:
  - explicit ingredient nutrition records
  - recipe-level nutrition objects
  - debuggable ingredient contribution breakdowns
  - preserved honest unknown semantics
- Phase B can now build balanced-meal scoring on `estimated_nutrition_per_serving` without needing another recipe corpus first.

## Phase B - Balanced Meal Scoring

### Status

PASS

### Root Cause Found

- PantryPilot already had calorie, budget, variety, and meal-role logic, but it still ranked lunch/dinner choices mostly on cost, calorie fit, and repetition pressure.
- Main-versus-side separation existed, but there was no explicit balance score to prefer protein/vegetable/carb composition for mains or complement gaps with sides.
- Dessert, beverage, and condiment suppression already existed as filtering heuristics, but there was no explainable scoring layer reinforcing meal realism during ranking.

### Files Inspected

- `pantry_pilot/planner.py`
- `pantry_pilot/models.py`
- `tests/test_phase6_planning.py`
- `tests/test_phase6_regressions.py`
- `tests/test_phase10_pantry_roles.py`
- `tests/test_phaseB_balance_scoring.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `pantry_pilot/planner.py`
- `tests/test_phaseB_balance_scoring.py`
- `docs/recipe_planner_fix_plan.md`

### Scoring Model

- Added an explainable `MealBalanceScore` layer in `pantry_pilot/planner.py`.
- The scorer uses explicit meal-composition signals for lunch/dinner:
  - `protein-support`
  - `vegetable-support`
  - `carb-support`
  - `anchor-composition`
  - `complements-main`
- It also applies explainable penalties for weak or unrealistic selections:
  - `penalty:side-like-main`
  - `penalty:weak-anchor`
  - `penalty:low-sustainability`
  - `penalty:non-meal-title`
  - hard penalties for `condiment`, `dessert`, `beverage`, and `snack`
- Main scoring:
  - rewards mains that look like anchors with at least two of protein / vegetable / carb support
  - penalizes side-like or obviously weak mains
- Side scoring:
  - rewards sides that add components missing from the main
  - lightly penalizes overlap with the main when the side does not improve composition
- The score is soft:
  - it modifies ranking cost
  - it does not override allergen safety, calorie constraints, known-price checks, or the weekly budget gate
- Added a planner flag `balance_scoring_enabled` so before/after behavior can be verified on the same codebase without changing UI behavior.

### Exact Diff

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
+PROTEIN_SUPPORT_INGREDIENTS = frozenset(...)
+VEGETABLE_SUPPORT_INGREDIENTS = frozenset(...)
+CARB_SUPPORT_INGREDIENTS = frozenset(...)
@@
+@dataclass(frozen=True)
+class MealBalanceScore:
+    total: float
+    components: frozenset[str]
+    reasons: tuple[str, ...]
@@
+        balance_scoring_enabled: bool = True,
@@
+        self.balance_scoring_enabled = balance_scoring_enabled
@@
+            balance_score = self._meal_balance_score(
+                recipe,
+                desired_slot,
+                candidate_role,
+                anchor_recipe,
+            )
+            effective_cost -= balance_score.total
@@
+    def _meal_balance_score(
+        self,
+        recipe: Recipe,
+        desired_slot: str,
+        candidate_role: str,
+        anchor_recipe: Recipe | None,
+    ) -> MealBalanceScore:
+        ...
+
+    def _meal_component_tags(self, recipe: Recipe) -> frozenset[str]:
+        ...
```

```diff
diff --git a/tests/test_phaseB_balance_scoring.py b/tests/test_phaseB_balance_scoring.py
@@
+class BalanceScoringPhaseTests(unittest.TestCase):
+    def test_balanced_meals_score_above_weak_meals(self) -> None:
+        ...
+
+    def test_side_pairing_improves_meal_composition(self) -> None:
+        ...
+
+    def test_dessert_drink_and_condiment_titles_are_not_chosen_as_main_lunch_dinner_meals(self) -> None:
+        ...
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phaseB_balance_scoring
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase10_pantry_roles
```

```powershell
@'
... weekly before/after balance demo using the same recipe pool with balance_scoring_enabled=False vs True ...
'@ | C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -
```

### Before/After Behavior

- Controlled weekly before/after demo:
  - before balance scoring:
    - most days paired `Chicken Plate` mains with cheaper starch sides such as `Lemon Rice 4`, `Lemon Rice 7`, `Lemon Rice 3`, `Lemon Rice 2`, `Lemon Rice 6`, `Lemon Rice 5`
  - after balance scoring:
    - the same `Chicken Plate` anchors were instead paired with vegetable sides across the week such as `Broccoli Salad 5`, `Broccoli Salad 1`, `Broccoli Salad 7`, `Broccoli Salad 3`, `Broccoli Salad 6`, `Broccoli Salad 4`
- Explainable score example from the same demo:
  - main: `MealBalanceScore(total=2.35, components={'carb', 'protein'}, reasons=('protein-support', 'carb-support', 'anchor-composition'))`
  - side: `MealBalanceScore(total=1.75, components={'vegetable'}, reasons=('vegetable-support', 'complements-main'))`
- This is the intended shift:
  - mains stay as the anchor
  - sides fill missing composition gaps instead of defaulting to the cheapest starch-heavy option when a better complement is feasible
- Real dataset smoke still succeeds:
  - first 7 selected real-dataset meals after the patch:
    - `['Hot Dog Stew(Ww Ii Stew)', 'Mediterranean Salad', 'Chowder Parmesan', 'Indian Fish And Potato Bake', 'Thai Cucumbers', 'Avocado Paletas', 'Italian Zucchini']`
  - `REAL_DATASET_MAIN_COUNT 7`
  - `REAL_DATASET_TOTAL_COST 36.3`

### Verification Result

- New balance-scoring tests passed:
  - `Ran 3 tests in 0.020s`
  - `OK`
- Fast regression suite still passed:
  - `Ran 8 tests in 72.649s`
  - `OK`
- Pantry carryover and meal-role suite still passed:
  - `Ran 6 tests in 71.757s`
  - `OK`
- No major regressions were introduced in budget, calorie, carryover, or role-planning behavior in the exercised suites.

### Readiness For Phase C

- Ready for Phase C.
- The planner now has a soft, explainable meal-balance layer that can:
  - distinguish strong anchors from weak mains
  - prefer complementary sides
  - reinforce realistic lunch/dinner choices during ranking
- The next phase can refine grocery/package economics on top of these stronger meal-selection decisions.

## Phase C - Grocery Economics Refinement

### Status

PASS

### Root Cause Found

- Pantry carryover already existed, and the planner already separated consumed cost from added shopping cost, but grocery economics still broke down in edge cases where package math depended on more than one unit conversion step.
- The unit conversion helper only supported direct and one-step reverse conversions, so some common grocery products could not be priced realistically when the recipe unit, PantryPilot ingredient unit, and store package unit differed.
- That left MVP pricing less trustworthy for cases like `package -> item -> oz` or `item -> cup -> tbsp`, and it weakened carryover realism for packaged ingredients.

### Files Inspected

- `pantry_pilot/ingredient_catalog.py`
- `pantry_pilot/planner.py`
- `pantry_pilot/pantry_carryover.py`
- `pantry_pilot/providers.py`
- `tests/test_phase6_regressions.py`
- `tests/test_phase10_pantry_roles.py`
- `tests/test_phaseB_balance_scoring.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `pantry_pilot/ingredient_catalog.py`
- `tests/test_phaseC_grocery_economics.py`
- `docs/recipe_planner_fix_plan.md`

### Cost-Model Changes

- Replaced direct-only ingredient unit conversion with a small graph-based offline conversion resolver:
  - standard unit conversions still apply
  - ingredient-specific conversions are added as explicit edges
  - breadth-first traversal now supports multi-step conversions when needed
- Added curated ingredient-specific package and container conversions for common MVP ingredients used in weekly planning and shopping:
  - `cream cheese`
  - `sour cream`
  - `cheddar cheese`
  - `mozzarella cheese`
  - `evaporated milk`
- Kept the existing economics separation intact:
  - `consumed_cost` remains what the meal actually used
  - `incremental_cost` remains what that meal forced the user to buy now
  - pantry leftovers remain available for carryover into later plans
- The price model remains local and stable:
  - no live grocery API dependence was introduced
  - curated package math sits on top of the existing mock/provider architecture

### Exact Diff

```diff
diff --git a/pantry_pilot/ingredient_catalog.py b/pantry_pilot/ingredient_catalog.py
@@
+from collections import deque
@@
+    ("cheddar cheese", "package", "cup"): 2.0,
+    ("cream cheese", "package", "item"): 1.0,
+    ("mozzarella cheese", "package", "cup"): 2.0,
+    ("sour cream", "item", "cup"): 2.0,
+    ("evaporated milk", "item", "cup"): 1.5,
@@
-def convert_ingredient_unit_quantity(...):
-    ... direct / reverse only ...
+def convert_ingredient_unit_quantity(
+    ingredient_name: str,
+    quantity: float,
+    from_unit: str,
+    to_unit: str,
+) -> float | None:
+    normalized_from = canonical_unit_name(from_unit)
+    normalized_to = canonical_unit_name(to_unit)
+    if normalized_from == normalized_to:
+        return quantity
+
+    conversion_graph = _build_conversion_graph(canonical_ingredient_name(ingredient_name))
+    if normalized_from not in conversion_graph:
+        return None
+
+    queue: deque[tuple[str, float]] = deque([(normalized_from, 1.0)])
+    visited = {normalized_from}
+    while queue:
+        unit, factor = queue.popleft()
+        for neighbor, edge_factor in conversion_graph.get(unit, {}).items():
+            if neighbor in visited:
+                continue
+            next_factor = factor * edge_factor
+            if neighbor == normalized_to:
+                return quantity * next_factor
+            visited.add(neighbor)
+            queue.append((neighbor, next_factor))
+    return None
+
+def _build_conversion_graph(canonical_name: str) -> dict[str, dict[str, float]]:
+    ...
```

```diff
diff --git a/tests/test_phaseC_grocery_economics.py b/tests/test_phaseC_grocery_economics.py
new file mode 100644
@@
+class GroceryEconomicsPhaseCTests(unittest.TestCase):
+    def test_common_conversion_case_sour_cream_item_to_cup_prices_correctly(self) -> None:
+        ...
+
+    def test_common_conversion_case_cream_cheese_package_prices_correctly(self) -> None:
+        ...
+
+    def test_multi_step_conversion_case_prices_correctly(self) -> None:
+        ...
+
+    def test_package_reuse_across_weeks_keeps_consumed_and_added_cost_separate(self) -> None:
+        ...
+
+    def test_meal_cost_presentation_does_not_collapse_to_whole_package_cost(self) -> None:
+        ...
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phaseC_grocery_economics
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase10_pantry_roles tests.test_phaseB_balance_scoring
```

### Before/After Behavior

- Before cost example:
  - a requirement of `1 package cream cheese` against a product sold as `8 oz` had no reliable direct conversion path
  - old logic only handled direct or reverse lookups, so `package -> item -> oz` could not be resolved as a single estimate
- After cost example:
  - `1 package cream cheese` now resolves through explicit multi-step conversion
  - verified result:
    - `estimated_packages = 1`
    - `package_quantity = 8.0`
    - `package_unit = 'oz'`
    - `estimated_cost = 2.5`
- Before cost presentation:
  - a meal consuming `1 cup` from a `2 cup` sour cream package could be mistaken for a full-package meal cost in edge cases
- After cost presentation:
  - the meal cost remains separated honestly:
    - `incremental_cost = 2.8`
    - `consumed_cost = 1.4`
  - this preserves the distinction between what the meal used and what the user had to buy
- Multi-week carryover example:
  - week 1:
    - `estimated_packages = 4`
    - `estimated_total_cost = 11.2`
    - `leftover_quantity_remaining = 1.0 cup`
    - first meal:
      - `incremental_cost = 2.8`
      - `consumed_cost = 1.4`
  - week 2 using carryover:
    - `estimated_packages = 3`
    - `estimated_total_cost = 8.4`
    - `carryover_used_quantity = 1.0 cup`
    - first meal:
      - `incremental_cost = 0.0`
      - `consumed_cost = 1.4`
- This is the intended economics behavior:
  - added shopping goes down when pantry carryover exists
  - meal consumption value stays stable
  - whole-package pricing is not misreported as per-meal consumption

### Verification Result

- New grocery economics tests passed:
  - `Ran 5 tests in 0.059s`
  - `OK`
- Fast regression suite still passed:
  - `Ran 8 tests in 92.237s`
  - `OK`
- Balance scoring and pantry-role regressions still passed:
  - `Ran 9 tests in 92.116s`
  - `OK`
- No previously fixed planner regressions reappeared in the exercised suites:
  - budget compliance still passed
  - pantry-role planning still passed
  - balance-scoring behavior still passed

### Whether Another Dataset Is Still Justified

- Not yet.
- The remaining issues addressed in this phase were planner economics issues, not recipe-corpus insufficiency.
- RecipeNLG should remain the primary corpus until nutrition, balance, and grocery economics improvements are fully absorbed and any remaining coverage gaps are measured directly.

## Decision Phase - Real Nutrition Data Selection and Integration Design

### Status

PASS

### Root Cause / Current Gap

- PantryPilot's current ingredient nutrition support is still heuristic and hand-curated.
- The current balanced-meal layer is useful, but it still relies heavily on internal heuristics rather than an official food-group guidance model.
- The repo needed an evidence-based decision about whether USDA FoodData Central and MyPlate / Dietary Guidelines are a strong fit before starting any larger ingestion work.

### Sources Evaluated

- USDA FoodData Central
  - Foundation Foods
  - SR Legacy
  - FNDDS
- Dietary Guidelines for Americans / MyPlate

### Chosen Source(s)

- Nutrition source:
  - local USDA FoodData Central snapshot
  - priority order:
    1. `Foundation Foods`
    2. `SR Legacy`
    3. `FNDDS` fallback for common generic prepared pantry ingredients
- Healthy-meal guidance source:
  - `MyPlate + Dietary Guidelines for Americans`

### Why Chosen

- FoodData Central is the best fit because it is:
  - official USDA data
  - public-domain / CC0
  - downloadable as local JSON/CSV snapshots
  - suitable for version pinning and local planner-time lookup
  - compatible with explicit, reviewable ingredient mapping
- Foundation Foods is the strongest primary fit for PantryPilot commodity ingredients.
- SR Legacy broadens coverage without forcing runtime network use.
- FNDDS is a useful fallback for generic prepared pantry ingredients such as tortillas or condensed soups.
- MyPlate / Dietary Guidelines are the best fit for balance guidance because they provide:
  - official food-group framing
  - explainable meal composition logic
  - a better basis for soft scoring than ad hoc title-only rules
- Safest MVP choice:
  - use MyPlate / Dietary Guidelines as `soft scoring guidance`, not hard planner rules.

### Mapping Sample Coverage

- Created a small USDA pilot artifact:
  - `docs/usda_mapping_sample.json`
- Pilot used a representative `20`-ingredient PantryPilot sample against official USDA downloadable snapshots:
  - Foundation Foods
  - SR Legacy
  - FNDDS
- Reviewed results:
  - `15/20` clean matches
  - `4/20` partial / needs curated disambiguation
  - `1/20` no clean match
- Representative clean examples:
  - `apple -> Apples, fuji, with skin, raw`
  - `broccoli -> Broccoli, raw`
  - `cilantro -> Coriander (cilantro) leaves, raw`
  - `cream cheese -> Cream cheese, full fat, block`
  - `olive oil -> Olive oil`
  - `zucchini -> Squash, summer, green, zucchini, includes skin, raw`
- Representative partial/failure cases:
  - `cheddar cheese`
    - nearest pilot hit favored a cheese-spread variant rather than plain cheddar
  - `flour tortillas`
    - pilot could land on assembled taco records instead of the pantry ingredient
  - `stuffing mix`
    - likely usable only via a packaged/prepared generic fallback
  - `tofu`
    - pilot found fried tofu rather than a plain tofu baseline
  - `garam masala`
    - no clean generic USDA match in the pilot

### Expected Coverage Limits

- Commodity and minimally processed ingredients should have high expected macro coverage for:
  - calories
  - protein
  - carbs
  - fat
- Generic pantry processed staples should have moderate-to-high coverage once SR Legacy and FNDDS fallback are added.
- Mixed spice blends and some specialty pantry items will still require:
  - curated mapping
  - or explicit unknowns
- Honest unknown behavior must remain unchanged:
  - no trusted mapping -> no nutrition value
  - no fake zero values

### Runtime-Safety Design

- Do not use USDA API lookups in planner runtime.
- Use pinned local USDA snapshots instead.
- No giant one-shot ingestion job.
- Required processing model:
  - chunked mapping batches
  - resumable checkpoints
  - file-backed outputs
  - compact local derived nutrition table for runtime
- Required pilot-first workflow:
  - start with `20-30` ingredients
  - save candidate lists
  - review ambiguous mappings
  - only then expand
- Required checkpoint artifacts:
  - `usda_snapshot_manifest.json`
  - `usda_compact_foods.jsonl`
  - `mapping_candidates.jsonl`
  - `mapping_decisions.jsonl`
  - `derived_pantrypilot_nutrition.json`
- Success criteria for the next implementation phase:
  - at least `70%` clean pilot mapping
  - explicit surfacing of ambiguous cases
  - restartable runs
  - local-only planner lookup

### Files Inspected

- `pantry_pilot/ingredient_catalog.py`
- `pantry_pilot/nutrition.py`
- `pantry_pilot/recipe_estimation.py`
- `pantry_pilot/planner.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `docs/nutrition_data_plan.md`
- `docs/usda_mapping_sample.json`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/docs/nutrition_data_plan.md b/docs/nutrition_data_plan.md
new file mode 100644
@@
+# Real Nutrition Data Selection and Integration Design
+...
+## Recommendation
+...
+## Proof Of Fit: Representative PantryPilot Ingredient Sample
+...
+## Runtime-Safety Design
+...
```

```diff
diff --git a/docs/usda_mapping_sample.json b/docs/usda_mapping_sample.json
new file mode 100644
@@
+{
+  "source_urls": {
+    "foundation": "...FoodData_Central_foundation_food_json_2025-12-18.zip",
+    "sr_legacy": "...FoodData_Central_sr_legacy_food_json_2018-04.zip",
+    "fndds": "...FoodData_Central_survey_food_json_2024-10-31.zip"
+  },
+  "sample_size": 20,
+  "results": [...]
+}
```

### Verification Result

- Official-source evaluation supports the chosen stack:
  - FoodData Central downloadable snapshots exist in JSON/CSV
  - Foundation Foods and SR Legacy are USDA-backed
  - FNDDS is available as a USDA survey-food fallback
  - FoodData Central data are public-domain / CC0
  - the API exists but is rate-limited and key-based, so it should not be runtime-critical
- Small proof-of-fit completed on a real PantryPilot ingredient sample.
- The chosen healthy-meal guidance source is confirmed:
  - MyPlate / Dietary Guidelines should be used as `soft scoring guidance`
  - not as hard medical or hard failure rules

### Recommended Next Implementation Phase

- `Phase D - USDA Nutrition Pilot Integration`
- Scope:
  - add a tiny local USDA snapshot pipeline
  - add checkpointed mapping candidate generation
  - add a compact derived nutrition table for a `20-30` ingredient pilot
  - add tests for resume behavior, ambiguous mapping handling, and local-only runtime lookup

## Phase D - Real Nutrition Data Integration Pilot

### Status

PASS

### Root Cause Found

- PantryPilot had a usable but heuristic nutrition layer.
- The repo needed the smallest safe production-quality pilot of a real nutrition source without starting a broad USDA ingestion job.
- The highest-value pilot target was a small explicit USDA-backed subset that:
  - improves real RecipeNLG nutrition output
  - uses local file-backed runtime lookups
  - keeps unknowns honest
  - avoids long-running mapping/bootstrap work

### Files Inspected

- `pantry_pilot/nutrition.py`
- `pantry_pilot/ingredient_catalog.py`
- `pantry_pilot/recipe_estimation.py`
- `pantry_pilot/providers.py`
- `tests/test_phase11_nutrition.py`
- `docs/nutrition_data_plan.md`
- `docs/usda_mapping_sample.json`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `pantry_pilot/nutrition.py`
- `pantry_pilot/ingredient_catalog.py`
- `pantry_pilot/recipe_estimation.py`
- `pantry_pilot/data/usda_nutrition_pilot_manifest.json`
- `pantry_pilot/data/usda_nutrition_pilot_mappings.json`
- `pantry_pilot/data/usda_nutrition_pilot_records.json`
- `tests/test_phaseD_usda_nutrition_pilot.py`
- `docs/recipe_planner_fix_plan.md`

### Pilot Coverage

- Implemented a checked-in local USDA pilot cache for `9` PantryPilot canonical ingredients:
  - `broccoli`
  - `cheddar cheese`
  - `cilantro`
  - `cream cheese`
  - `cream of mushroom soup`
  - `granola`
  - `olive oil`
  - `sour cream`
  - `soy sauce`
- Runtime behavior:
  - planner-time nutrition lookups now read these pilot records from local JSON files
  - no USDA API calls are used in planner runtime
  - no broad ingestion or long mapping job is required for this phase
- Fallback behavior:
  - pilot-mapped ingredients prefer USDA-backed local records
  - non-pilot ingredients continue using the existing heuristic layer
  - unmapped ingredients remain unknown

### Exact Diff

```diff
diff --git a/pantry_pilot/nutrition.py b/pantry_pilot/nutrition.py
@@
+import json
+from functools import lru_cache
+from pathlib import Path
@@
+    source_dataset: str = ""
+    source_food_id: int | None = None
+    source_description: str = ""
+    source_release: str = ""
+    pilot: bool = False
@@
+USDA_PILOT_MANIFEST_PATH = DATA_DIR / "usda_nutrition_pilot_manifest.json"
+USDA_PILOT_RECORDS_PATH = DATA_DIR / "usda_nutrition_pilot_records.json"
+USDA_PILOT_MAPPINGS_PATH = DATA_DIR / "usda_nutrition_pilot_mappings.json"
@@
+def pilot_nutrition_record_keys() -> tuple[str, ...]:
+    ...
+
+def pilot_nutrition_mapping_keys() -> tuple[str, ...]:
+    ...
+
+def ingredient_nutrition_key(value: str, *, include_usda_pilot: bool = True) -> str | None:
+    ...
+
+def lookup_ingredient_nutrition(value: str, *, include_usda_pilot: bool = True) -> IngredientNutritionRecord | None:
+    ...
+
+def _load_usda_pilot_records() -> dict[str, IngredientNutritionRecord]:
+    ...
+
+def _load_usda_pilot_mappings() -> dict[str, str]:
+    ...
```

```diff
diff --git a/pantry_pilot/recipe_estimation.py b/pantry_pilot/recipe_estimation.py
@@
-def estimate_recipe_nutrition(ingredients, servings):
+def estimate_recipe_nutrition(ingredients, servings, *, use_usda_pilot: bool = True):
@@
-        record = lookup_ingredient_nutrition(ingredient.name)
+        record = lookup_ingredient_nutrition(ingredient.name, include_usda_pilot=use_usda_pilot)
@@
-def estimate_calories_per_serving(ingredients, servings):
+def estimate_calories_per_serving(ingredients, servings, *, use_usda_pilot: bool = True):
```

```diff
diff --git a/pantry_pilot/ingredient_catalog.py b/pantry_pilot/ingredient_catalog.py
@@
+    ("cream of mushroom soup", "item", "can"): 1.0,
+    ("cream of mushroom soup", "can", "cup"): 1.25,
```

```diff
diff --git a/pantry_pilot/data/usda_nutrition_pilot_records.json b/pantry_pilot/data/usda_nutrition_pilot_records.json
new file mode 100644
@@
+{
+  "records": [
+    { "key": "usda-fdc-pilot:cream-cheese-plain-cup", ... },
+    { "key": "usda-fdc-pilot:sour-cream-regular-cup", ... },
+    { "key": "usda-fdc-pilot:cream-of-mushroom-soup-condensed-cup", ... },
+    ...
+  ]
+}
```

```diff
diff --git a/tests/test_phaseD_usda_nutrition_pilot.py b/tests/test_phaseD_usda_nutrition_pilot.py
new file mode 100644
@@
+class UsdaNutritionPilotPhaseTests(unittest.TestCase):
+    def test_pilot_mapped_ingredients_resolve_deterministically(self) -> None:
+        ...
+
+    def test_unsupported_ingredients_stay_unknown(self) -> None:
+        ...
+
+    def test_recipe_level_nutrition_improves_for_pilot_covered_real_examples(self) -> None:
+        ...
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phaseD_usda_nutrition_pilot tests.test_phase11_nutrition
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions tests.test_phaseB_balance_scoring tests.test_phase10_pantry_roles
```

```powershell
@'
... local verification script computing pilot ingredient count, real-dataset before/after recipe coverage, example recipe breakdowns, unknown handling, and lookup timing ...
'@ | C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -
```

### Before/After Behavior

- Pilot ingredient coverage:
  - `PILOT_INGREDIENT_COUNT 9`
- Real RecipeNLG recipes touching the pilot subset:
  - `PILOT_RECIPE_COUNT 5427`
- Recipe nutrition coverage on those recipes:
  - `BEFORE_RECIPE_NUTRITION_COVERAGE 1706`
  - `AFTER_RECIPE_NUTRITION_COVERAGE 3314`
  - `IMPROVED_RECIPE_COUNT 1608`
- Improved real recipe examples:
  - `"Guacamole Dip"`
  - `"Hot Onion Dip"`
  - `"Great" Meat Loaf`
  - plus many more such as:
    - `"Dare to be Different " Dip`
    - `"Dippin Apples"`
    - `"Po Boys" Delight`
    - `(Easy) Creamy Crock-Pot Chicken And Mushrooms`
- Example breakdowns after the pilot:
  - `"Guacamole Dip"`
    - before: `None`
    - after: `NutritionEstimate(calories=421, protein_grams=6.2, carbs_grams=17.5, fat_grams=38.1)`
  - `"Hot Onion Dip"`
    - before: `None`
    - after: `NutritionEstimate(calories=662, protein_grams=17.9, carbs_grams=8.4, fat_grams=61.4)`
  - `"Great" Meat Loaf`
    - before: `None`
    - after: `NutritionEstimate(calories=713, protein_grams=43.0, carbs_grams=16.1, fat_grams=52.0)`
- Honest unknown proof remains intact:
  - `UNKNOWN_EXAMPLE_PER_SERVING None`
  - `UNKNOWN_EXAMPLE_MISSING ('garam masala',)`
- Runtime behavior:
  - `RUNTIME_FIRST_LOOKUP_MS 0.008`
  - `RUNTIME_REPEAT_1000_LOOKUPS_MS 1.869`
  - `RUNTIME_FIRST_LOOKUP_SOURCE usda-fdc-pilot`

### Verification Result

- Focused USDA pilot and nutrition tests passed:
  - `Ran 6 tests in 0.015s`
  - `OK`
- Fast regression suites still passed:
  - `Ran 17 tests in 129.328s`
  - `OK`
- No planner-time network dependency was introduced.
- No broad ingestion/bootstrap job was added in this pilot.
- Unknown or ambiguous ingredients still remain unknown instead of becoming fake zeroes.

### Recommended Next Phase

- `Phase E - USDA Nutrition Pilot Expansion And Guidance Wiring`
- Scope:
  - expand the USDA-backed subset to the next reviewed ingredient batch
  - add an optional checkpointed mapper for future batch growth
  - start wiring MyPlate / Dietary Guidelines food-group tags into the balance scorer
  - continue keeping runtime local, restartable, and honest about unknowns

## Phase E - USDA Nutrition Pilot Expansion And Guidance Wiring

### Status

PASS

### Root Cause Found

- The USDA-backed pilot was still too narrow to unblock a large share of real RecipeNLG recipes.
- Balanced-meal scoring still depended mostly on hardcoded ingredient buckets, so MyPlate-style food-group guidance was not yet influencing planner ranking in an explicit, inspectable way.
- The next safe step was not a broad USDA ingestion job. It was:
  - another reviewed checked-in ingredient batch
  - plus explicit local meal-guidance tags wired into the existing soft scorer

### Files Inspected

- `docs/recipe_planner_fix_plan.md`
- `docs/nutrition_data_plan.md`
- `docs/usda_mapping_sample.json`
- `pantry_pilot/nutrition.py`
- `pantry_pilot/planner.py`
- `pantry_pilot/ingredient_catalog.py`
- `pantry_pilot/providers.py`
- `pantry_pilot/recipe_estimation.py`
- `tests/test_phaseD_usda_nutrition_pilot.py`
- `tests/test_phaseB_balance_scoring.py`

### Files Changed

- `pantry_pilot/nutrition.py`
- `pantry_pilot/planner.py`
- `pantry_pilot/ingredient_catalog.py`
- `pantry_pilot/data/usda_nutrition_pilot_manifest.json`
- `pantry_pilot/data/usda_nutrition_pilot_mappings.json`
- `pantry_pilot/data/usda_nutrition_pilot_records.json`
- `pantry_pilot/data/usda_meal_guidance_tags.json`
- `tests/test_phaseD_usda_nutrition_pilot.py`
- `tests/test_phaseE_usda_expansion_guidance.py`
- `docs/recipe_planner_fix_plan.md`

### Expanded Mapping Coverage

- USDA-backed mapped ingredients before: `9`
- USDA-backed mapped ingredients after: `24`
- New reviewed batch added:
  - `bacon`
  - `baking powder`
  - `baking soda`
  - `cayenne pepper`
  - `cherries`
  - `cocoa`
  - `coconut`
  - `cream of chicken soup`
  - `evaporated milk`
  - `green onion`
  - `heavy cream`
  - `mustard`
  - `nutmeg`
  - `pecans`
  - `thyme`
- Honest unknowns were preserved for weak cases:
  - `garam masala` still remains unmapped and unknown
  - `stuffing mix` was allowed into guidance tags only, not force-mapped into nutrition yet

### Guidance Wiring Approach

- Added a local checked-in meal-guidance table at `pantry_pilot/data/usda_meal_guidance_tags.json`.
- Guidance stays soft:
  - no hard meal failures
  - no medical rules
  - no allergen or budget rule changes
- Guidance is now explicit and debuggable:
  - `food_group_tags` such as `protein_foods`, `vegetables`, `grains`, `dairy`
  - `component_tags` such as `protein`, `vegetable`, `carb`
- Planner wiring:
  - `_meal_component_tags()` now uses local guidance tags first, then existing heuristic/macronutrient fallback
  - `_meal_balance_score()` now adds explicit guidance reasons:
    - `guidance:protein_foods`
    - `guidance:vegetables`
    - `guidance:grains_starches`
    - `guidance:dairy`
- This means guidance signals can now influence ranking while current calorie, budget, allergen, and safety constraints remain intact.

### Exact Diff

```diff
diff --git a/pantry_pilot/nutrition.py b/pantry_pilot/nutrition.py
@@
+@dataclass(frozen=True)
+class IngredientGuidanceRecord:
+    canonical_ingredient: str
+    food_group_tags: frozenset[str]
+    component_tags: frozenset[str]
+    source: str = "myplate-guidance"
+    notes: str = ""
+USDA_MEAL_GUIDANCE_PATH = DATA_DIR / "usda_meal_guidance_tags.json"
+def guidance_mapping_keys() -> tuple[str, ...]:
+    ...
+def lookup_ingredient_guidance(value: str) -> IngredientGuidanceRecord | None:
+    ...
```

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
+from pantry_pilot.nutrition import lookup_ingredient_guidance
+@dataclass(frozen=True)
+class MealGuidanceProfile:
+    food_group_tags: frozenset[str]
+    component_tags: frozenset[str]
@@
+        meal_guidance_enabled: bool = True,
@@
+        guidance = self._meal_guidance_profile(recipe)
+        if "protein_foods" in guidance.food_group_tags:
+            reasons.append("guidance:protein_foods")
+        if guidance.food_group_tags & {"vegetables", "vegetables_legumes", "vegetables_starchy"}:
+            reasons.append("guidance:vegetables")
+        if guidance.food_group_tags & {"grains", "grains_starches", "vegetables_starchy"}:
+            reasons.append("guidance:grains_starches")
+        if "dairy" in guidance.food_group_tags:
+            reasons.append("guidance:dairy")
@@
+    def _meal_guidance_profile(self, recipe: Recipe) -> MealGuidanceProfile:
+        ...
```

```diff
diff --git a/pantry_pilot/ingredient_catalog.py b/pantry_pilot/ingredient_catalog.py
@@
+    ("cream of chicken soup", "item", "can"): 1.0,
+    ("cream of chicken soup", "can", "cup"): 1.25,
```

```diff
diff --git a/pantry_pilot/data/usda_nutrition_pilot_mappings.json b/pantry_pilot/data/usda_nutrition_pilot_mappings.json
@@
- 9 reviewed pilot mappings
+24 reviewed local USDA-backed mappings

diff --git a/pantry_pilot/data/usda_nutrition_pilot_records.json b/pantry_pilot/data/usda_nutrition_pilot_records.json
@@
- 9 reviewed pilot records
+24 reviewed local USDA-backed records

diff --git a/pantry_pilot/data/usda_meal_guidance_tags.json b/pantry_pilot/data/usda_meal_guidance_tags.json
new file mode 100644
@@
+33 explicit local guidance mappings for protein / vegetables / grains-starches / dairy
```

```diff
diff --git a/tests/test_phaseE_usda_expansion_guidance.py b/tests/test_phaseE_usda_expansion_guidance.py
new file mode 100644
@@
+def test_expanded_usda_mappings_resolve_deterministically(...)
+def test_unknowns_remain_unknown_when_mapping_is_weak(...)
+def test_recipe_level_nutrition_improves_for_phase_e_examples(...)
+def test_balance_scoring_uses_guidance_signals(...)
```

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phaseD_usda_nutrition_pilot tests.test_phaseE_usda_expansion_guidance tests.test_phase11_nutrition
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions tests.test_phaseB_balance_scoring tests.test_phase10_pantry_roles
```

```powershell
@'
... local verification script comparing Phase D vs Phase E coverage, printing improved RecipeNLG examples, honest unknown proof, runtime timing, and guidance-off vs guidance-on weekly plans ...
'@ | C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -
```

### Before/After Behavior

- USDA-backed mapped ingredient count:
  - before: `9`
  - after: `24`
- Real RecipeNLG nutrition coverage:
  - before: `12045`
  - after: `22196`
  - newly improved recipes: `10151`
- Example newly improved real recipes:
  - `15 Minute Chicken And Rice Dinner`
    - before: `None`
    - after: `NutritionEstimate(calories=569, protein_grams=57.6, carbs_grams=27.3, fat_grams=15.7)`
    - newly covered ingredient contribution included:
      - `cream of chicken soup`
  - `"Cocktail Meatballs"`
    - before: `None`
    - after: `NutritionEstimate(calories=572, protein_grams=34.6, carbs_grams=21.7, fat_grams=37.5)`
    - newly covered ingredient contribution included:
      - `thyme`
  - `" Add In Anything" Muffins!`
    - before: `None`
    - after: `NutritionEstimate(calories=635, protein_grams=8.5, carbs_grams=70.7, fat_grams=35.5)`
    - newly covered ingredient contributions included:
      - `baking powder`
      - `baking soda`
- Honest unknown proof:
  - `UNKNOWN_GARAM_MASALA None`
  - `UNKNOWN_RECIPE_PER_SERVING None`
  - `UNKNOWN_RECIPE_MISSING ('garam masala',)`
- Guidance influence proof:
  - controlled weekly-plan example with guidance off:
    - `['Potato Plate 1', 'Potato Plate 3', 'Potato Plate 5', 'Potato Plate 7', 'Bacon Potato Skillet 2', 'Potato Plate 6', 'Potato Plate 2']`
  - same weekly-plan example with guidance on:
    - `['Bacon Potato Skillet 2', 'Potato Plate 3', 'Potato Plate 5', 'Potato Plate 7', 'Potato Plate 2', 'Potato Plate 1', 'Potato Plate 6']`
  - score for `Bacon Potato Skillet`:
    - before guidance: `MealBalanceScore(total=-0.8, ...)`
    - after guidance: `MealBalanceScore(total=3.69, ...)`
    - new explicit reasons:
      - `guidance:protein_foods`
      - `guidance:vegetables`
      - `guidance:grains_starches`
- Runtime summary:
  - `RUNTIME_FIRST_LOOKUP_MS 0.004`
  - `RUNTIME_REPEAT_1000_LOOKUPS_MS 1.787`
  - `RUNTIME_LOOKUP_SOURCE usda-fdc-pilot`

### Verification Result

- Focused nutrition + guidance suites:
  - `Ran 10 tests in 0.027s`
  - `OK`
- Fast regression suites:
  - `Ran 17 tests in 177.118s`
  - `OK`
- No live USDA API calls were added to planner runtime.
- No broad ingestion/bootstrap job was added in this phase.
- Guidance is now influencing balance scoring while budget, calorie, allergen, and safety behavior stayed intact in the exercised regression suites.

### Recommended Next Phase

- `Phase F - Reviewed USDA Batch Expansion Tooling`
- Scope:
  - add a tiny chunked checkpointed review tool for the next explicit mapping batch
  - keep planner runtime on the compact checked-in local cache
  - expand reviewed savory staples before attempting long-tail baking or spice cleanup

## Finish-Line Roadmap

This section supersedes the earlier immediate-next-phase note above. The project focus has shifted from proving individual subsystems to finishing PantryPilot as a trustworthy weekly meal-planning application.

### Phase F - Data Finalization and Runtime Contract

#### Goal

- Lock PantryPilot's runtime data contract so the website always loads deterministic local data with explicit provenance, stable fallbacks, and honest unknown handling.

#### Scope

- define the final runtime-owned local data artifacts for:
  - RecipeNLG recipe loading
  - USDA-backed reviewed nutrition mappings
  - local meal-guidance tags
  - grocery pricing/catalog support
- remove ambiguity about which artifacts are planner-time dependencies versus offline build/review artifacts
- make runtime loading behavior explicit:
  - what is required
  - what is optional
  - what causes planner failure versus honest unknown output
- document and test cache invalidation / snapshot version expectations

#### What Success Means

- planner/runtime inputs are explicit and deterministic
- no hidden dependency on ad hoc generated files, live APIs, or stale intermediate artifacts
- failures explain which required runtime contract element is missing
- local runtime data can be loaded repeatably in development and demo use

#### What Must Not Change

- RecipeNLG remains the main recipe corpus
- planner runtime stays local/offline for nutrition and guidance lookups
- unknown allergen data remains unsafe
- honest unknown nutrition/cost behavior remains intact

#### How To Verify It

- run runtime-contract tests that validate expected local data files and failure messages
- verify planner startup and plan generation succeed from the documented local runtime contract only
- verify removing a required runtime artifact fails clearly rather than silently degrading
- verify removing an optional support artifact preserves honest unknown behavior

### Phase G - Planner Deliberation Architecture

#### Goal

- Make planner choice behavior more deliberate, inspectable, and stable so mains and sides are chosen for clear reasons rather than as side effects of loosely coupled heuristics.

#### Scope

- restructure meal selection into a clearer deliberation flow:
  - anchor main candidate evaluation
  - side complement evaluation
  - weekly tradeoff selection
- make selection reasons first-class planner outputs for debugging and UI display
- reduce accidental weak-main selection, unstable tie behavior, and confusing weekly sequencing
- improve internal diagnostics for why a recipe won or lost

#### What Success Means

- lunch/dinner mains are consistently anchor-like
- optional sides are selected to complement the anchor when feasible
- planner decisions are explainable with stable reason strings or score components
- repeated requests on the same inputs produce stable, believable outputs

#### What Must Not Change

- existing safety, allergen, calorie, and budget constraints remain intact
- cuisine preferences remain soft, not hard filters
- pantry carryover and cost separation remain intact
- this phase does not add another recipe dataset

#### How To Verify It

- add targeted tests for main-anchor prioritization and side complement selection
- run fixed-input weekly-plan snapshots and confirm stable output / rationale
- verify dessert/drink/condiment candidates do not reappear as lunch/dinner mains
- rerun the fast regression suite

### Phase H - Weekly Balance and Sustainability

#### Goal

- Improve whole-week realism so PantryPilot produces plans that feel sustainable across several days, not just individually plausible meal slots.

#### Scope

- add week-level scoring and guardrails for:
  - protein and vegetable presence across the week
  - overuse of identical meal styles
  - sustainability of lunch/dinner anchors across consecutive days
  - pantry reuse without creating unrealistic repetition
- improve weekly reasoning around leftovers, cost, and variety tradeoffs
- make weekly balance explanations available for inspection

#### What Success Means

- weekly plans look more believable across all seven days
- the planner avoids drifting into repetitive starch-heavy or side-like weekly outputs
- pantry reuse lowers shopping pressure without collapsing variety
- plan explanations can summarize week-level tradeoffs honestly

#### What Must Not Change

- food-group guidance remains soft scoring guidance, not medical enforcement
- unknowns remain unknown instead of turning into invented precision
- budget compliance and shopping-list honesty remain intact
- UI redesign is not the focus of this phase

#### How To Verify It

- compare before/after weekly-plan examples on fixed requests
- add tests for week-level variety, balance, and repetition control
- verify pantry carryover still reduces added shopping without misreporting meal consumption cost
- rerun planner regression coverage

### Phase I - Website Trust and Readability

#### Goal

- Present PantryPilot results clearly and honestly in the website so users can understand what was selected, what is known versus unknown, and why the plan is believable.

#### Scope

- improve result presentation for:
  - selected mains and sides
  - nutrition summaries
  - consumed cost vs added shopping
  - pantry carryover
  - planner rationale / selection reasons
  - planner failure messages
- tighten wording and layout so the site communicates confidence, limits, and tradeoffs directly
- improve readability without changing the core product direction or adding a redesign-heavy detour

#### What Success Means

- users can quickly see what each day includes and why it was chosen
- costs and nutrition are presented honestly, with unknowns clearly marked
- pantry reuse and added shopping are easy to understand
- planner failures are understandable and actionable rather than vague

#### What Must Not Change

- no misleading certainty where data is incomplete
- no hiding of unknown nutrition, pricing, or safety gaps
- no change to core safety rules
- this phase does not replace Streamlit without a strong reason

#### How To Verify It

- run manual website checks on representative requests
- add UI-level tests or output assertions for key labels and rationale sections
- verify the website clearly distinguishes consumed meal cost from added shopping cost
- verify unknown values are labeled honestly and planner failure messaging remains truthful

### Phase J - Final Acceptance and Project Lock

#### Goal

- Close the project with an explicit acceptance pass that confirms PantryPilot meets the weekly meal-planning finish line and can be handed in or demoed confidently.

#### Scope

- define the final acceptance checklist across:
  - runtime determinism
  - planner quality
  - nutrition estimation
  - grocery economics
  - pantry carryover
  - explanation quality
  - website trust/readability
- clean up remaining low-risk inconsistencies
- freeze the final documented workflow and verification steps

#### What Success Means

- PantryPilot can generate believable weekly meal plans from the documented runtime data contract
- planner outputs are explainable and site presentation is trustworthy
- the required regression and acceptance checks all pass
- the repo has a clear final state, not an open-ended experimental roadmap

#### What Must Not Change

- no late-stage giant dataset addition unless the repo has new evidence that RecipeNLG is insufficient
- no weakening of allergen safety or honest unknown behavior
- no hidden runtime dependency on live services
- no scope creep into unrelated product experiments

#### How To Verify It

- run the final acceptance suite and manual demo checklist
- capture one or more final representative weekly plans and review them against the finish-line goals
- verify the documented runtime contract and setup instructions are sufficient for a clean run
- mark the project locked only if all required checks pass without caveats

## Phase F - Data Finalization and Runtime Contract

### Status

PASS

### Root Cause / Current Gap

- PantryPilot had the right local runtime pieces, but the active runtime contract still lived in scattered code paths:
  - recipe loading in `pantry_pilot/providers.py`
  - nutrition/guidance files in `pantry_pilot/nutrition.py`
  - pantry carryover in `pantry_pilot/pantry_carryover.py`
  - pricing behavior in `pantry_pilot/providers.py` and `pantry_pilot/app_runtime.py`
- That made it harder to prove which local files were truly active, whether sample fallback was being used accidentally, and what the current coverage / weak spots looked like on the real runtime path.

### Files Inspected

- `docs/recipe_planner_fix_plan.md`
- `docs/nutrition_data_plan.md`
- `pantry_pilot/providers.py`
- `pantry_pilot/nutrition.py`
- `pantry_pilot/app_runtime.py`
- `pantry_pilot/pantry_carryover.py`
- `pantry_pilot/planner.py`
- `tests/test_phase2_providers.py`
- `tests/test_phase6_regressions.py`

### Files Changed

- `pantry_pilot/providers.py`
- `pantry_pilot/runtime_audit.py`
- `docs/runtime_data_contract.md`
- `tests/test_phaseF_runtime_contract.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/providers.py b/pantry_pilot/providers.py
@@
+@dataclass(frozen=True)
+class RecipeRuntimeStatus:
+    processed_dataset_path: Path
+    processed_dataset_exists: bool
+    processed_recipe_count: int
+    active_source: str
+    fallback_active: bool
+    fallback_reason: str = ""
+    sample_recipe_count: int = 0
+
+def resolve_recipe_runtime(...) -> tuple[tuple[Recipe, ...], RecipeRuntimeStatus]:
+    ...
```

```diff
diff --git a/pantry_pilot/runtime_audit.py b/pantry_pilot/runtime_audit.py
new file mode 100644
@@
+class RuntimeDataContract(...)
+class RuntimeCoverageAudit(...)
+def build_runtime_data_contract(...) -> RuntimeDataContract:
+def build_runtime_coverage_audit(...) -> RuntimeCoverageAudit:
+def render_runtime_audit_text(...) -> str:
+python -m pantry_pilot.runtime_audit [--json]
```

```diff
diff --git a/docs/runtime_data_contract.md b/docs/runtime_data_contract.md
new file mode 100644
@@
+# PantryPilot Runtime Data Contract
+## Active Runtime Contract
+## Runtime Audit Path
+## Normal-Path Expectations
+## Failure Expectations
```

```diff
diff --git a/tests/test_phaseF_runtime_contract.py b/tests/test_phaseF_runtime_contract.py
new file mode 100644
@@
+def test_runtime_contract_reports_active_processed_dataset_and_local_support_files(...)
+def test_runtime_audit_reports_current_coverage_without_recipe_fallback(...)
+def test_missing_dataset_reports_sample_fallback_state(...)
```

### Data Contract

- Active recipe corpus path:
  - `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
- Active recipe source in the normal path:
  - `processed-dataset`
- Allowed recipe fallback:
  - `pantry_pilot.sample_data`
- Active local nutrition support files:
  - `pantry_pilot/data/usda_nutrition_pilot_manifest.json`
  - `pantry_pilot/data/usda_nutrition_pilot_mappings.json`
  - `pantry_pilot/data/usda_nutrition_pilot_records.json`
- Active local guidance support file:
  - `pantry_pilot/data/usda_meal_guidance_tags.json`
- Active pantry carryover path:
  - `data/pantry_carryover.json`
- Active pricing behavior:
  - default runtime pricing source is `mock`
  - real-store mode is optional
  - provider unavailability falls back to `mock`
- Runtime determinism rules:
  - planner-time nutrition is local/offline only
  - planner-time guidance is local/offline only
  - sample recipe fallback is not expected in the normal path

See:
- `docs/runtime_data_contract.md`

### Verification Command(s)

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phaseF_runtime_contract
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase2_providers tests.test_phase6_regressions
```

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m pantry_pilot.runtime_audit --json
```

### Coverage Results

- Active runtime paths:
  - recipe corpus:
    - `C:\Users\Legom\mae301-2026spring-PantryPilot\mvp\data\processed\recipenlg-full-20260416T0625Z.json`
  - nutrition manifest:
    - `C:\Users\Legom\mae301-2026spring-PantryPilot\pantry_pilot\data\usda_nutrition_pilot_manifest.json`
  - nutrition mappings:
    - `C:\Users\Legom\mae301-2026spring-PantryPilot\pantry_pilot\data\usda_nutrition_pilot_mappings.json`
  - nutrition records:
    - `C:\Users\Legom\mae301-2026spring-PantryPilot\pantry_pilot\data\usda_nutrition_pilot_records.json`
  - guidance:
    - `C:\Users\Legom\mae301-2026spring-PantryPilot\pantry_pilot\data\usda_meal_guidance_tags.json`
  - pantry carryover:
    - `C:\Users\Legom\mae301-2026spring-PantryPilot\data\pantry_carryover.json`
- Runtime contract state:
  - `active_recipe_source = processed-dataset`
  - `recipe_fallback_active = false`
  - `processed_recipe_count = 23021`
  - `default_pricing_source = mock`
  - `mock_price_catalog_count = 102`
  - `runtime_local_only_for_nutrition = true`
  - `runtime_local_only_for_guidance = true`
- Coverage audit:
  - `total_recipes = 23021`
  - `meal_type_counts = {'breakfast': 3539, 'dinner': 19482, 'lunch': 845}`
  - `inferred_role_counts = {'beverage': 186, 'condiment': 2248, 'dessert': 5015, 'main': 14352, 'side': 1220}`
  - `nutrition_recipe_count = 22196`
  - `calorie_recipe_count = 22444`
  - `priced_recipe_count = 21444`
  - `nutrition_unknown_count = 825`
  - `calorie_unknown_count = 577`
  - `price_unknown_count = 1577`
  - `allergen_unknown_count = 0`
  - `weak_main_count = 7293`
  - `usda_mapped_ingredient_count = 24`
  - `guidance_mapping_count = 35`
- Current explicit weak spots:
  - `nutrition_unknowns_present`
  - `pricing_unknowns_present`
  - `weak_mains_present`

### Proof The Normal Path Is Not Using Accidental Fallback

- `resolve_recipe_runtime(DEFAULT_PROCESSED_RECIPES_PATH)` now reports:
  - `active_source = processed-dataset`
  - `fallback_active = false`
- The runtime audit command on the default app/runtime path reports the same state.
- A dedicated test also verifies the opposite behavior on a missing dataset path:
  - `active_source = sample-fallback`
  - `fallback_reason = processed dataset path does not exist`

### Verification Result

- Focused Phase F runtime-contract suite passed:
  - `Ran 3 tests in 12.489s`
  - `OK`
- Provider + regression suites passed:
  - `Ran 17 tests in 201.997s`
  - `OK`
- The new runtime audit command ran successfully on the real dataset and returned the expected processed-dataset normal path.

### Recommended Next Phase

- `Phase G - Planner Deliberation Architecture`
- Reason:
  - the runtime data layer is now explicit and auditable
  - the main remaining weakness is planner quality and weekly realism rather than uncertainty about which runtime files are active

## Phase G - Planner Deliberation Architecture

### Status

PASS

### Root Cause

- The planner already had better nutrition, guidance, and economics inputs, but selection still felt opaque because most winning logic lived inside one monolithic candidate ranking pass.
- That made it harder to prove:
  - which candidates survived hard constraints
  - which candidates passed main/side role gating
  - why a main anchor beat weaker lunch/dinner options
  - why a side complemented the chosen main
  - whether repeated identical requests were rotating only across genuinely near-equal plans
- The practical symptom was that planner quality still looked like weak weighted ranking instead of deliberate staged selection.

### Files Inspected

- `pantry_pilot/planner.py`
- `tests/test_phaseB_balance_scoring.py`
- `tests/test_phase10_pantry_roles.py`
- `tests/test_phase6_regressions.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `pantry_pilot/planner.py`
- `tests/test_phaseG_planner_deliberation.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
-class ChoiceCandidate:
-    ...
+class SelectionOutcome:
+    selected: CandidateDeliberation
+    hard_constraint_count: int
+    role_gate_count: int
+    diversity_peer_count: int
+    runner_up_title: str | None
+    runner_up_margin: float | None
@@
-class MealSelectionDiagnostic:
-    candidate_count: int
+class MealSelectionDiagnostic:
+    hard_constraint_count: int
+    role_gate_count: int
+    runner_up_title: str | None
+    runner_up_margin: float | None
@@
-def _best_choice(...) -> CandidateDeliberation | None:
+def _best_choice(...) -> SelectionOutcome | None:
+    # explicit stages:
+    # 1. hard constraint filtering
+    # 2. role gating
+    # 3. main/side ranking
+    # 4. weekly diversity peer selection
@@
+def _passes_candidate_role_gate(...) -> bool:
+    ...
@@
-def _is_diversity_peer(candidate_key, best_key) -> bool:
+def _is_diversity_peer(candidate, best) -> bool:
+    ...
@@
-("main-ranking" if candidate_role == "main" else "side-ranking", ...)
+("hard-constraint-filter", 1.0)
+("role-gating", ...)
+("main-candidate-ranking" if candidate_role == "main" else "side-candidate-ranking", ...)
+("weekly-diversity-adjustment", ...)
+("pantry-cost-adjustment", ...)
+("calorie-adjustment", ...)
```

```diff
diff --git a/tests/test_phaseG_planner_deliberation.py b/tests/test_phaseG_planner_deliberation.py
new file mode 100644
@@
+def test_strong_mains_outrank_weak_mains(...)
+def test_side_pairing_reasoning_is_visible(...)
+def test_repeated_identical_requests_only_vary_among_near_equal_plans(...)
```

### Deliberation Model

- Stage 1: hard constraint filtering
  - reject candidates that break calorie support, price support, weekly budget, or repeat-cap rules
- Stage 2: role gating
  - apply explicit lunch/dinner anchor confidence for mains
  - keep side gating explicit for side candidates
  - allow fallback to the hard-constraint pool only when the gated pool would be empty
- Stage 3: role-aware ranking
  - mains use stronger anchor confidence plus balance/guidance signals
  - sides use complement-to-main scoring more aggressively than before
- Stage 4: weekly diversity adjustment
  - repeats, recent repeats, cuisine repetition, and near-duplicate pressure are separate stage signals
- Stage 5: pantry/cost adjustment
  - pantry matches, preferred cuisine, incremental cost, and budget pressure remain explicit
- Stage 6: diversity peer selection
  - repeated identical requests only rotate across candidates that remain close after stage scoring, not across clearly weaker meals
- Selection diagnostics now expose:
  - chosen title
  - hard-constraint survivor count
  - role-gated survivor count
  - runner-up title and score margin when present
  - stage scores
  - signal reasons such as `main-anchor:strong`, `complements-main`, `budget-pressure`, and `calorie-alignment`

### Verification Command(s)

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phaseG_planner_deliberation tests.test_phaseB_balance_scoring
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase10_pantry_roles tests.test_phase6_regressions
```

```powershell
@'
...one-off planner verification script capturing strong-main choice, side diagnostics, and near-peer rotation...
'@ | & .\.venv\Scripts\python.exe -
```

### Before / After Behavior

- Main-anchor choice:
  - before this phase, main wins were explainable only indirectly through the old sort key
  - after this phase, the planner exposes explicit stage diagnostics
  - example:
    - winner: `Chicken Broccoli Rice Bowl`
    - diagnostic:
      - `hard_constraint_count = 2`
      - `role_gate_count = 1`
      - `stage_scores` include `hard-constraint-filter`, `role-gating`, `main-candidate-ranking`, `weekly-diversity-adjustment`, `pantry-cost-adjustment`, `calorie-adjustment`
      - reasons include `main-anchor:strong`
- Side pairing:
  - before the final Phase G adjustment, the side path was still willing to pick `Lemon Rice` over `Broccoli Salad` because pantry/cost adjustment could outweigh complement quality
  - after the fix, the same case selects:
    - main: `Chicken Plate`
    - side: `Broccoli Salad`
    - side diagnostic:
      - `runner_up_title = Lemon Rice`
      - `runner_up_margin = 0.24`
      - reasons include `guidance:vegetables`, `vegetable-support`, `complements-main`
- Repeated identical requests:
  - after the diversity-peer tightening, three identical requests rotated only across a close peer set:
    - `Chicken Rice Bowl`
    - `Herby Rice Bowl`
    - `Turkey Rice Bowl`
  - the recorded `diversity_peer_count` was `3` for each run
  - the weak option `Buttered Pasta` did not enter that rotation set

### Proof Outputs Are More Intentional

- Chosen meals now carry explicit staged reasoning instead of only an implicit final sort key.
- Main-anchor confidence is now strong enough to reduce weak lunch/dinner mains more reliably.
- Side selection now visibly favors complementary composition over a small cost edge.
- Diversity variation is now bounded to near peers instead of looser weak-vs-strong mixing.

### Verification Result

- Focused Phase G + balance suites:
  - `Ran 6 tests in 0.125s`
  - `OK`
- Regression suites:
  - `Ran 14 tests in 258.616s`
  - `OK`

### Recommended Next Phase

- `Phase H - Weekly Balance and Sustainability`
- Reason:
  - candidate-level selection is now more deliberate and diagnosable
  - the next gap is week-level realism across days, not just single-slot choice quality

## Phase H - Weekly Balance and Sustainability

### Status

PASS

### Root Cause

- Phase G made single-slot selection more deliberate, but the week could still drift into patterns that felt repetitive over several days:
  - the same starch base appearing too often
  - protein and produce variety not being rewarded strongly enough across the whole week
  - side selection complementing the current main, but not always diversifying the week-level side mix
  - repeated cuisine / meal-structure / anchor-pattern pressure still living mostly inside generic repetition signals rather than an explicit week-sustainability layer
- The result was that plans could be locally sensible while still feeling less sustainable over a full 7-day run.

### Files Inspected

- `pantry_pilot/planner.py`
- `tests/test_phaseG_planner_deliberation.py`
- `tests/test_phaseB_balance_scoring.py`
- `tests/test_phase10_pantry_roles.py`
- `tests/test_phase6_regressions.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `pantry_pilot/planner.py`
- `tests/test_phaseH_weekly_balance.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
+class WeeklyVarietyScore:
+    total: float
+    reasons: tuple[str, ...]
@@
 class VarietyProfile:
+    protein_variety_bonus: float
+    produce_variety_bonus: float
+    repeated_starch_penalty: float
+    repeated_meal_structure_penalty: float
+    repeated_anchor_pattern_penalty: float
+    side_diversity_bonus: float
+    repeated_side_pairing_penalty: float
@@
-        meal_guidance_enabled: bool = True,
+        meal_guidance_enabled: bool = True,
+        week_balance_enabled: bool = True,
@@
+def _weekly_variety_score(...) -> WeeklyVarietyScore:
+    ...
+def _primary_protein_key(...) -> str | None:
+def _produce_keys(...) -> frozenset[str]:
+def _primary_starch_key(...) -> str | None:
+def _meal_structure_pattern_key(...) -> str:
+def _anchor_pattern_key(...) -> str:
+def _anchor_side_pairing_key(...) -> str:
@@
     stage_scores=(
         ("hard-constraint-filter", 1.0),
         ("role-gating", ...),
         ("main-candidate-ranking" | "side-candidate-ranking", ...),
         ("weekly-diversity-adjustment", ...),
+        ("week-level-balance-adjustment", ...),
         ("pantry-cost-adjustment", ...),
         ("calorie-adjustment", ...),
     )
```

```diff
diff --git a/tests/test_phaseH_weekly_balance.py b/tests/test_phaseH_weekly_balance.py
new file mode 100644
@@
+def test_reduced_week_level_repetition(...)
+def test_improved_variety_across_the_week(...)
+def test_better_side_diversity(...)
```

### Week-Level Scoring Changes

- Added an explicit `week-level-balance-adjustment` stage on top of the Phase G selection pipeline.
- Main-level weekly signals now include:
  - protein variety reward
  - produce variety reward
  - repeated starch penalty
  - repeated cuisine penalty once a cuisine is already dominating the week
  - repeated meal-structure penalty
  - repeated anchor-pattern penalty
- Side-level weekly signals now include:
  - side component diversity reward
  - side produce diversity reward
  - repeated side-structure penalty
  - repeated main+side pairing penalty
  - vegetable-side balance reward when the week needs more produce-forward sides
- These remain soft ranking signals only. Budget enforcement, calorie enforcement, allergen safety, honest unknown handling, and pantry carryover behavior were left intact.

### Verification Command(s)

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phaseH_weekly_balance tests.test_phaseG_planner_deliberation tests.test_phaseB_balance_scoring
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase10_pantry_roles tests.test_phase6_regressions
```

```powershell
@'
...one-off Phase H verification script comparing week_balance_enabled=False vs True on a controlled weekly dinner pool...
'@ | & .\.venv\Scripts\python.exe -
```

### Before / After Behavior

- Controlled weekly example:
  - before:
    - first day selected `Beef Potato Plate`
    - first side selected `Tomato Salad`
    - first-day `week-level-balance-adjustment = 0.0`
  - after:
    - first day selected `Lentil Tomato Stew`
    - first side selected `Green Bean Salad`
    - first-day `week-level-balance-adjustment = 3.15`
- Why the improved week is more sustainable:
  - the main now wins partly because the planner can see explicit `weekly:protein-variety` and `weekly:produce-variety` value instead of only local meal fit
  - the side now wins partly because the planner can see `weekly:side-diversity`, `weekly:side-produce-variety`, and `weekly:vegetable-side-balance`
  - repeated starch / repeated anchor pressure can now push obviously repetitive week patterns down even when the single-meal score is still acceptable

### Measurable Variety Metrics

- Week-level scorer checks from the targeted tests:
  - after a rice-heavy history, a repeated `Chicken Rice Bowl` candidate scores below `Beef Potato Plate`
  - reasons on the repeated candidate now include:
    - `weekly:repeated-starch`
    - `weekly:repeated-anchor-pattern`
  - after a mixed but partially repetitive week history, `Lentil Tomato Stew` scores above `Turkey Rice Bowl`
  - reasons on the more sustainable candidate include:
    - `weekly:protein-variety`
    - `weekly:produce-variety`
  - after repeated `Broccoli Salad` side usage, `Tomato Salad` scores above another `Broccoli Salad`
  - reasons on the improved side include:
    - `weekly:side-produce-variety`

### Verification Result

- Focused Phase H + Phase G + balance suites:
  - `Ran 9 tests in 0.238s`
  - `OK`
- Regression suites:
  - `Ran 14 tests in 442.767s`
  - `OK`

### Recommended Next Phase

- `Phase I - Website Trust and Readability`
- Reason:
  - the planner now has explicit local data, deliberate slot-level selection, and week-level sustainability scoring
  - the remaining finish-line gap is helping users understand and trust the plan output in the website

## Phase I - Website Trust and Readability

### Status

PASS

### Root Cause

- The planner had become materially better, but the website was still presenting many outputs as raw numbers without enough trust framing:
  - meal rationale lived in planner diagnostics, not in the UI
  - ingredient-based nutrition existed, but weekly and meal-level nutrition summaries were not clearly surfaced
  - consumed cost vs added shopping cost existed, but the trust semantics were still easy to miss
  - partial or lower-confidence estimates were not labeled clearly enough
- In addition, temporary runtime failures could still look like planner bugs instead of transient system issues, especially when the user already had a valid previous plan.

### Files Inspected

- `mvp/app.py`
- `pantry_pilot/app_runtime.py`
- `pantry_pilot/plan_display.py`
- `pantry_pilot/plan_failures.py`
- `pantry_pilot/models.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase10_pantry_roles.py`
- `tests/test_phase6_regressions.py`
- `docs/recipe_planner_fix_plan.md`

### Files Changed

- `mvp/app.py`
- `pantry_pilot/app_runtime.py`
- `pantry_pilot/plan_display.py`
- `pantry_pilot/plan_failures.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase10_pantry_roles.py`
- `tests/test_phaseI_ui_reliability.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/plan_display.py b/pantry_pilot/plan_display.py
@@
+class WeeklyNutritionSummary:
+    ...
+def meal_total_nutrition(...) -> NutritionEstimate | None:
+def summarize_weekly_nutrition(...) -> WeeklyNutritionSummary:
+def format_optional_nutrition(...) -> str:
+def format_estimate_confidence_label(...) -> str:
+def confidence_note(...) -> str | None:
+def compact_selection_rationale(...) -> str:
+def summarize_plan_balance(...) -> str:
+def summarize_carryover_usage(...) -> str:
@@
-def build_plan_text_export(...):
+def build_plan_text_export(..., selection_diagnostics=()):
+    # include weekly nutrition, carryover summary, plan-balance summary,
+    # meal confidence labels, rationale, and uncertainty notes
```

```diff
diff --git a/mvp/app.py b/mvp/app.py
@@
+from pantry_pilot.plan_display import compact_selection_rationale, confidence_note, ...
+from pantry_pilot.plan_failures import build_runtime_failure_feedback, is_transient_runtime_failure
@@
+Weekly Nutrition / Carryover Used / Plan Balance summary cards
+meal-level confidence labels
+meal-level nutrition strings
+compact why-chosen captions
+partial-estimate notes
@@
+preserve last successful plan on failures
+classify temporary runtime failures separately from planner-fit failures
```

```diff
diff --git a/pantry_pilot/plan_failures.py b/pantry_pilot/plan_failures.py
@@
+GENERIC_RUNTIME_FAILURE_HEADLINE = ...
+TRANSIENT_RUNTIME_MARKERS = ...
+def is_transient_runtime_failure(...) -> bool:
+def build_runtime_failure_feedback(...) -> tuple[str, list[str]]:
```

```diff
diff --git a/tests/test_phaseI_ui_reliability.py b/tests/test_phaseI_ui_reliability.py
new file mode 100644
@@
+def test_transient_runtime_failures_are_classified_honestly(...)
```

### UI / Readability Changes

- Weekly summary now communicates:
  - total shopping cost
  - weekly nutrition summary
  - pantry carryover used
  - plan-balance summary
- Each meal now communicates:
  - role (`main` / `side`)
  - meal nutrition
  - consumed cost
  - added shopping cost
  - compact “Why chosen” summary
  - confidence label (`Estimated`, `Partial estimate`, or `Lower-confidence estimate`)
  - note when a meal is partially estimated or weaker-confidence
- Text export now mirrors the trust framing instead of only dumping titles and costs.
- Reliability pass:
  - temporary runtime failures such as “high demand” are now labeled as temporary runtime problems
  - the app preserves the last successful plan on screen when a new request fails
  - retry guidance is now different for transient/system failures vs real planner-fit failures

### Verification Command(s)

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase2_app_display tests.test_phase10_pantry_roles tests.test_phaseI_ui_reliability
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
@'
...one-off snapshot export script...
'@ | & .\.venv\Scripts\python.exe -
```

### Before / After Behavior

- Before:
  - meal cards showed calories and costs, but not ingredient-level nutrition or compact rationale
  - uncertainty was mostly implicit
  - temporary backend/runtime failures could read like PantryPilot logic failures
- After:
  - each meal shows a compact rationale, confidence label, meal nutrition, consumed cost, and added shopping cost
  - weekly summary shows nutrition, carryover use, and a plan-balance summary
  - partial estimates are called out explicitly
  - temporary runtime failures now get a retry-oriented message and preserve the last successful plan

Practical output example from the export path:

```text
Weekly nutrition: 6,334 cal estimated | P 298.0g | C 700.0g | F 263.8g
Carryover summary: No pantry carryover was used this week.
Plan balance summary: 7 strong-anchor meals, 3 complementary sides, 12 week-balance adjustments.

Dinner: Hot Dog Stew(Ww Ii Stew) (main) | Unknown | consumed $3.25 | added shopping $3.60 | 592 calories
  Nutrition: 592 cal | P 16.2g | C 134.4g | F 1.0g
  Confidence: Estimated
  Why chosen: adds protein variety, adds produce variety, strong anchor.
```

### Evidence The Website Communicates Decisions And Uncertainty Better

- “Why chosen” summaries now expose planner intent directly from the selection diagnostics.
- Confidence labels now distinguish between fully estimated meals and partially estimated meals.
- Weekly trust framing now separates:
  - pantry carryover use
  - weekly nutrition
  - plan balance
  - cost semantics
- Temporary system/runtime issues now have a dedicated failure path instead of being mixed into ordinary planning failures.

### Verification Result

- Focused Phase I display + snapshot + reliability suites:
  - `Ran 10 tests in 194.307s`
  - `OK`
- Regression suite:
  - `Ran 8 tests in 194.129s`
  - `OK`

### Recommended Next Phase

- `Phase J - Final Acceptance and Project Lock`
- Reason:
  - the data contract, planner behavior, weekly sustainability, and website trust/readability layers are now in place
  - the remaining work is final acceptance validation, final cleanup, and project lock-down

## Phase J - Final Acceptance and Project Lock

### Root Cause / Remaining Gap

- PantryPilot had reached a stable planner/runtime shape, but the project still needed a frozen acceptance path that:
  - runs a small set of real demo scenarios reproducibly
  - proves the website/runtime export path still renders safely
  - documents the exact runtime files used for demo/submission
  - records remaining limitations honestly

### Acceptance Scenarios

- `balanced_week`
  - standard dinner-focused week on the active RecipeNLG + USDA-backed runtime path
- `tight_budget`
  - lower-budget week that must still complete inside budget
- `carryover_reuse`
  - two-run week proving pantry carryover inventory is created and then reused in later shopping
- `allergy_constrained`
  - dairy + peanut constrained week that must avoid forbidden allergens

### Runtime Freeze

- Active recipe corpus:
  - `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
- Active nutrition support:
  - `pantry_pilot/data/usda_nutrition_pilot_manifest.json`
  - `pantry_pilot/data/usda_nutrition_pilot_mappings.json`
  - `pantry_pilot/data/usda_nutrition_pilot_records.json`
- Active guidance support:
  - `pantry_pilot/data/usda_meal_guidance_tags.json`
- Active pricing path:
  - local mock provider by default
- Active pantry carryover behavior:
  - file-backed carryover store with leftover package quantities persisted between plans

### Changes

```diff
diff --git a/pantry_pilot/acceptance.py b/pantry_pilot/acceptance.py
@@
+--scenario CLI support
+per-scenario runtime timing
+carryover acceptance check based on actual reuse + reduced purchases
+frozen runtime + known limitation reporting
```

```diff
diff --git a/tests/test_phaseJ_acceptance.py b/tests/test_phaseJ_acceptance.py
new file mode 100644
@@
+selectable acceptance payload test
+rendered acceptance text contract test
```

```diff
diff --git a/mvp/report.md b/mvp/report.md
@@
+final acceptance command path
+frozen demo runtime files
+scenario outputs summary
+known limitations / readiness
```

### Verification Command(s)

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phaseJ_acceptance
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase2_app_display tests.test_phase10_pantry_roles tests.test_phaseI_ui_reliability
```

```powershell
& .\.venv\Scripts\python.exe -m pantry_pilot.acceptance --scenario balanced_week --json
& .\.venv\Scripts\python.exe -m pantry_pilot.acceptance --scenario tight_budget --json
& .\.venv\Scripts\python.exe -m pantry_pilot.acceptance --scenario carryover_reuse --json
& .\.venv\Scripts\python.exe -m pantry_pilot.acceptance --scenario allergy_constrained --json
```

### Acceptance Results

- `balanced_week`
  - `PASS`
  - `meal_count=12`
  - `main_count=7`
  - `side_count=5`
  - `estimated_total_cost=56.1`
  - `seconds=192.0`
  - export includes rationale, confidence labels, and weekly nutrition summary

- `tight_budget`
  - `PASS`
  - `meal_count=12`
  - `estimated_total_cost=17.0`
  - `remaining_budget=28.0`
  - `seconds=203.55`

- `carryover_reuse`
  - `PASS`
  - `first_week_cost=17.0`
  - `second_week_cost=17.15`
  - `baseline_second_week_cost_without_carryover=17.0`
  - `carryover_inventory_count_after_week1=6`
  - `second_week_carryover_used_items=6`
  - `second_week_carryover_used_quantity=9.5`
  - `second_week_reduced_purchase_items=4`
  - `seconds=665.89`
  - interpretation:
    - week-two total cost changed slightly because the planner chose a somewhat different week
    - the acceptance check is therefore based on real carryover reuse and reduced purchases, not forced identical week totals

- `allergy_constrained`
  - `PASS`
  - `meal_count=12`
  - `estimated_total_cost=49.15`
  - `forbidden_allergen_hits=[]`
  - `seconds=83.39`

### Frozen Coverage Snapshot

- `total_recipes=23021`
- `nutrition_recipe_count=22196`
- `priced_recipe_count=21444`
- `nutrition_unknown_count=825`
- `price_unknown_count=1577`
- `weak_main_count=7293`
- `usda_mapped_ingredient_count=24`
- `guidance_mapping_count=35`
- `recipe_fallback_active=false`
- `active_recipe_source=processed-dataset`

### Known Limitations

- Some recipe nutrition and pricing values remain partial because local USDA mappings and mock price coverage are not complete for every ingredient.
- Balanced-meal guidance is a soft scoring layer, not medical advice.
- Recipe quality still depends on RecipeNLG source cleanliness and role inference.
- Real-store pricing is optional and not part of the frozen demo/runtime contract.

### Verification Result

- `tests.test_phaseJ_acceptance`
  - `Ran 2 tests in 9.882s`
  - `OK`
- `tests.test_phase6_regressions`
  - `Ran 8 tests in 203.062s`
  - `OK`
- `tests.test_phase2_app_display tests.test_phase10_pantry_roles tests.test_phaseI_ui_reliability`
  - `Ran 10 tests in 201.146s`
  - `OK`
- acceptance scenarios:
  - `balanced_week PASS`
  - `tight_budget PASS`
  - `carryover_reuse PASS`
  - `allergy_constrained PASS`

### Final Readiness

- PantryPilot is now locked to a deterministic local runtime contract, has a reproducible acceptance command path, and passes the final demo scenarios on the active RecipeNLG + USDA-backed + mock-pricing stack.

## Phase K - Full USDA Nutrition Build

### Root Cause

- PantryPilot still depended on a small USDA-reviewed subset plus a larger heuristic nutrition table.
- That was good enough for planner experiments, but it was not a real production nutrition data layer:
  - the runtime contract still pointed at pilot files
  - the mapping process was not a full local USDA build
  - unresolved/ambiguous ingredients were not surfaced from a broad offline pass

### Files Changed

- `pantry_pilot/usda_build.py`
- `pantry_pilot/nutrition.py`
- `pantry_pilot/recipe_estimation.py`
- `pantry_pilot/runtime_audit.py`
- `tests/test_phaseK_usda_build.py`
- `tests/test_phaseF_runtime_contract.py`
- `docs/runtime_data_contract.md`
- `docs/recipe_planner_fix_plan.md`
- generated runtime artifacts:
  - `pantry_pilot/data/usda_nutrition_manifest.json`
  - `pantry_pilot/data/usda_nutrition_mappings.json`
  - `pantry_pilot/data/usda_nutrition_records.json`
  - `pantry_pilot/data/usda_nutrition_unresolved.json`

### Exact Diff Summary

```diff
diff --git a/pantry_pilot/usda_build.py b/pantry_pilot/usda_build.py
+ pinned USDA snapshot downloader
+ chunked/checkpointed compact-food extraction
+ deterministic ingredient candidate scoring
+ explicit reviewed USDA hint table
+ mapping manifest + unresolved report generation
+ compact runtime nutrition records generation
```

```diff
diff --git a/pantry_pilot/nutrition.py b/pantry_pilot/nutrition.py
+ full USDA runtime manifest / mappings / records paths
+ runtime_nutrition_mapping_keys()
+ runtime_nutrition_record_keys()
+ lookup_ingredient_nutrition_candidates()
+ runtime-first nutrition lookup ordering with source fallback preserved
```

```diff
diff --git a/pantry_pilot/recipe_estimation.py b/pantry_pilot/recipe_estimation.py
+ use_usda_full flag
+ source-ordered nutrition candidate fallback during unit conversion
```

```diff
diff --git a/pantry_pilot/runtime_audit.py b/pantry_pilot/runtime_audit.py
+ runtime contract now points at full USDA build artifacts
+ runtime coverage now reports full USDA mapping / record counts
```

### Build Design

- Source of truth:
  - USDA FoodData Central downloadable snapshots
  - priority order:
    1. `Foundation Foods`
    2. `SR Legacy`
    3. `FNDDS`
- Runtime remains local-only:
  - planner reads only the compact derived runtime files
  - planner does not read raw USDA snapshots directly
  - planner does not call the USDA API
- Offline build pipeline:
  - `python -m pantry_pilot.usda_build download`
  - `python -m pantry_pilot.usda_build build --reset`
- Build behavior:
  - reads local USDA snapshot zip files
  - extracts compact food rows with macro nutrients and portion hints
  - scores PantryPilot ingredient candidates deterministically
  - auto-accepts only strong matches
  - uses explicit reviewed hints for ambiguous high-frequency ingredients
  - writes:
    - compact runtime records
    - mapping manifest
    - unresolved / ambiguous report
    - checkpoint and candidate files under `pantry_pilot/data/nutrition_build/`
- Resumability:
  - dataset extraction is checkpointed per USDA dataset
  - ingredient mapping is processed in batches and resumed from `usda_build_checkpoint.json`

### Verification Command(s)

```powershell
& .\.venv\Scripts\python.exe -m pantry_pilot.usda_build download
& .\.venv\Scripts\python.exe -m pantry_pilot.usda_build build --reset --batch-size 50
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phaseK_usda_build
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase2_app_display tests.test_phase10_pantry_roles tests.test_phaseI_ui_reliability
```

```powershell
& .\.venv\Scripts\python.exe -m pantry_pilot.runtime_audit --json
```

### Before / After Coverage

- USDA-backed mapped ingredient count:
  - before: `24`
  - after: `88`
- USDA-backed runtime record count:
  - before: `24`
  - after: `87`
- recipe nutrition coverage:
  - before: `22196`
  - after: `22198`
- calorie/macros coverage:
  - before: `22196`
  - after: `22198`
- calorie support count:
  - before: `22444`
  - after: `22446`

Real RecipeNLG examples with materially changed full-build nutrition:

- `" Add In Anything" Muffins!`
  - before: `635 cal | P 8.5g | C 70.7g | F 35.5g`
  - after: `573 cal | P 9.6g | C 67.9g | F 27.2g`
- `"Amish" Friendship Bread`
  - before: `1796 cal | P 23.7g | C 328.9g | F 46.0g`
  - after: `1755 cal | P 28.2g | C 312.0g | F 17.5g`
- `"Apple Cake"`
  - before: `339 cal | P 2.5g | C 44.3g | F 17.8g`
  - after: `339 cal | P 3.0g | C 42.4g | F 7.1g`

### Remaining Unmapped Hotspots

Top remaining unmapped canonical ingredients by frequency:

- `bacon` (`903`) - ambiguous between meatless / turkey / prepared bacon variants
- `chicken breast` (`888`) - ambiguous between tenders / deli / prepared variants
- `raisins` (`863`) - ambiguous between plain and subtype records
- `soy sauce` (`713`) - multiple generic soy sauce records
- `chicken broth` (`481`) - broth vs bouillon vs condensed soup ambiguity
- `bell pepper` (`457`) - color-specific variants
- `rice vinegar` (`369`) - weak false-positive candidates in current snapshots
- `coconut` (`324`) - flour / oil / milk ambiguity
- `banana` (`237`) - ripe / overripe / raw variants
- `lime` (`141`) - lime vs lime juice ambiguity

### Timing

- full build time: `69.94s`
- runtime first lookup: `0.0311 ms`
- runtime repeated `1000` lookups: `1.1695 ms`

### Verification Result

- `tests.test_phaseK_usda_build`
  - `Ran 4 tests in 8.495s`
  - `OK`
- `tests.test_phase6_regressions`
  - `Ran 8 tests in 190.320s`
  - `OK`
- `tests.test_phase2_app_display tests.test_phase10_pantry_roles tests.test_phaseI_ui_reliability`
  - `Ran 10 tests in 188.666s`
  - `OK`

### Recommended Next Phase

- `Phase L - Unmapped Hotspot Review And Food-Group Enrichment`
- reason:
  - the runtime now has a real local USDA build contract
  - the next high-value step is targeted review of the remaining ambiguous high-frequency ingredients and expansion of guidance tags using the new broader USDA-backed layer

## Phase L - Personal Target Engine

### Status

PASS

### Root Cause

- PantryPilot already had real RecipeNLG runtime data, USDA-backed ingredient nutrition, local guidance tags, and deliberate weekly planning stages.
- What it still lacked was a user-specific target layer:
  - calorie targets were manual only
  - macro expectations were implicit, not user-shaped
  - food-group balance was generic rather than profile-aware
- That meant the app behaved like a better weekly planner, but not yet like a personal diet-planning assistant.

### Files Inspected

- `pantry_pilot/models.py`
- `pantry_pilot/planner.py`
- `pantry_pilot/plan_display.py`
- `pantry_pilot/app_runtime.py`
- `pantry_pilot/favorites.py`
- `mvp/app.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase6_regressions.py`
- `tests/test_phaseG_planner_deliberation.py`
- `tests/test_phaseH_weekly_balance.py`

### Files Changed

- `pantry_pilot/models.py`
- `pantry_pilot/personal_targets.py`
- `pantry_pilot/planner.py`
- `pantry_pilot/plan_display.py`
- `pantry_pilot/app_runtime.py`
- `pantry_pilot/favorites.py`
- `mvp/app.py`
- `tests/test_phaseL_personal_targets.py`
- `docs/recipe_planner_fix_plan.md`

### Target Model

- Added `UserNutritionProfile`
  - `age_years`
  - `sex`
  - `height_cm`
  - `weight_kg`
  - `activity_level`
  - `planning_goal`
- Added `PersonalNutritionTargets`
  - estimated calorie target and range
  - protein / carbs / fat target ranges
  - produce / grains-starches / protein-foods / dairy target amounts
  - explicit guidance note that the output is estimated planning support, not medical advice
- New module: `pantry_pilot/personal_targets.py`
  - uses adult energy-reference logic with activity coefficients
  - uses DRI-style macro ranges
  - uses MyPlate-style food-group targets by calorie band
  - keeps all outputs local and deterministic

### Planner Integration

- `PlannerRequest` can now carry:
  - `user_profile`
  - `personal_targets`
- Added a new planner stage:
  - `personal-target-adjustment`
- Added new target-aware reasons:
  - `target:protein-support`
  - `target:protein-range`
  - `target:low-protein`
  - `target:produce-support`
  - `target:produce-gap`
  - `target:grains-support`
  - `target:dairy-support`
  - `target:goal-high-protein`
  - `target:goal-low-protein`
  - `target:calorie-guidance`
- The target layer stays soft:
  - hard allergen safety unchanged
  - hard exclusions unchanged
  - budget enforcement unchanged
  - calorie enforcement unchanged
  - honest unknowns unchanged

### UI / Runtime Integration

- Minimal Streamlit inputs were added:
  - opt-in personal-target toggle
  - age / sex / height / weight / activity / goal
- The manual calorie slider still exists.
- When personal targets are enabled:
  - the request uses generated calorie targets for that run
  - the app shows estimated target summaries
  - exports include personal target guidance text
- Saved plans now round-trip the new nested request fields safely.

### Verification Command(s)

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phaseL_personal_targets tests.test_phase2_app_display tests.test_phaseB_balance_scoring tests.test_phaseG_planner_deliberation tests.test_phaseH_weekly_balance
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase2_app_display tests.test_phase10_pantry_roles tests.test_phaseI_ui_reliability
```

### Before / After Behavior

Before:

- calorie targeting was manual only
- no user profile model existed
- planner diagnostics could explain weekly balance, but not user-specific target fit
- website output did not surface any personal target guidance

After:

- PantryPilot can generate local profile-based planning targets
- the planner adds target-aware ranking signals and explanations
- the website shows estimated personal guidance summaries when enabled
- exports include personal target guidance alongside the week summary

Controlled profile example:

- lower-energy profile:
  - `30y female`
  - `160 cm`
  - `58 kg`
  - `sedentary`
  - `mild deficit`
- high-protein profile:
  - `34y female`
  - `168 cm`
  - `72 kg`
  - `low active`
  - `high protein preference`

Verified target-generation difference:

- lower-energy profile produces lower daily calories and lower protein minimums
- high-protein profile produces higher protein minimums and stronger protein-forward planner bonuses

Verified planner-ranking difference:

- in the controlled fixture, the score gap between `Chicken Protein Bowl` and `Garden Rice Bowl` grows materially under the high-protein profile
- target-specific reasons now appear in diagnostics, including `target:goal-high-protein` and `target:protein-range`

### Verification Result

- `tests.test_phaseL_personal_targets tests.test_phase2_app_display tests.test_phaseB_balance_scoring tests.test_phaseG_planner_deliberation tests.test_phaseH_weekly_balance`
  - `Ran 16 tests in 0.209s`
  - `OK`
- `tests.test_phase6_regressions`
  - `Ran 8 tests in 148.681s`
  - `OK`
- `tests.test_phase2_app_display tests.test_phase10_pantry_roles tests.test_phaseI_ui_reliability`
  - `Ran 10 tests in 149.511s`
  - `OK`

### Recommended Next Phase

- `Phase M - Profile-Aware Weekly Acceptance`
- reason:
  - the personal target engine now exists
  - the next step is acceptance-style validation on real RecipeNLG weekly plans for contrasting user profiles, with explicit website screenshots/output captures and known limitations around non-medical guidance

## Phase M - Performance Preservation and Progress Visibility

### Status

PASS

### Root Cause

- PantryPilot’s planner quality had improved phase after phase, but runtime cost had grown with it.
- Real app-path instrumentation showed repeated work dominating runtime:
  - repeated recipe-feature derivation
  - repeated guidance/component lookups
  - repeated recipe-role inference
  - repeated unit conversion and package-purchase evaluation
- The website also had no visible long-run progress, so a correct but expensive plan build could look frozen.

### Files Inspected

- `pantry_pilot/planner.py`
- `pantry_pilot/app_runtime.py`
- `mvp/app.py`
- `tests/test_phase6_regressions.py`

### Files Changed

- `pantry_pilot/planner.py`
- `pantry_pilot/app_runtime.py`
- `mvp/app.py`
- `tests/test_phaseM_performance_progress.py`
- `docs/recipe_planner_fix_plan.md`

### Bottleneck Analysis

Real app-path low-overhead instrumentation before optimization:

- total runtime: `225.0s`
- `_core_ingredient_names`: `11,355,905`
- `_meal_guidance_profile`: `2,839,319`
- `_meal_component_tags`: `2,693,438`
- `_package_purchase`: `2,339,879`
- `_convert_to_purchase_unit`: `2,330,440`
- `_meal_structure_pattern_key`: `1,183,520`
- `_primary_protein_key`: `1,023,416`
- `_recipe_role`: `1,019,484`

Main conclusion:

- most wasted work came from recomputing the same recipe-derived features over and over for the same RecipeNLG recipe objects
- the remaining major hotspot after that is pricing/package math

### Optimization Changes

- Added per-planner memoization for recipe-derived features:
  - core ingredient names
  - meal style markers
  - meal guidance profile
  - meal component tags
  - primary protein key
  - produce keys
  - primary starch key
  - meal structure pattern key
  - anchor pattern key
  - recipe role by desired slot
- Added small local caches for:
  - carryover quantity lookup
  - ingredient/unit conversion factor lookup
- Added a cache warm-up pass right after candidate filtering so repeated slot scoring reuses the same derived recipe state
- Preserved:
  - budget enforcement
  - calorie enforcement
  - allergen safety
  - personal target logic
  - main + side planning
  - week-level balance logic

### Progress Visibility Changes

- Added `PlanningProgress` updates from the planner
- New progress stages:
  - `setup`
  - `selection`
  - `finalize`
  - `complete`
- The Streamlit app now shows:
  - current stage label
  - slot/day label during selection
  - candidate counts in detail text
  - a monotonic progress bar
  - completion or failure messaging tied to the last completed stage

Sample progress output:

- `Loading candidates`
- `Candidates ready`
- `Planning Monday dinner`
- `Planning Tuesday dinner`
- `Plan ready`

### Verification Command(s)

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phaseM_performance_progress tests.test_phase6_regressions tests.test_phase2_app_display tests.test_phase10_pantry_roles tests.test_phaseI_ui_reliability
```

```powershell
@'
...real app-path instrumentation script...
'@ | & .\.venv\Scripts\python.exe -
```

### Before / After Timings

Same real app-path instrumentation command:

- before: `225.0s`
- after: `74.65s`

Key hot-call reductions:

- `_core_ingredient_names`
  - before: `11,355,905`
  - after: `2,318,995`
- `_meal_guidance_profile`
  - before: `2,839,319`
  - after: `191,923`
- `_meal_component_tags`
  - before: `2,693,438`
  - after: `818,659`
- `_meal_structure_pattern_key`
  - before: `1,183,520`
  - after: `649,478`
- `_primary_protein_key`
  - before: `1,023,416`
  - after: `489,374`

Remaining main hotspot:

- `_package_purchase` / `_convert_to_purchase_unit`
  - still around `2.33M` calls
  - planner runtime is now much better, but cost-path reuse is still the next obvious optimization frontier if another performance phase is needed

### Verification Result

- `tests.test_phaseM_performance_progress tests.test_phase6_regressions tests.test_phase2_app_display tests.test_phase10_pantry_roles tests.test_phaseI_ui_reliability`
  - `Ran 21 tests in 119.909s`
  - `OK`
- planner outputs preserved in practice:
  - fast regression suite still passes
  - display/render safety still passes
  - role/main-side/personal-target behavior still passes through existing regression coverage
- progress visibility proof:
  - callback now emits monotonic end-to-end progress states from `setup` through `complete`
  - app wiring uses those updates to render visible status and progress during long runs

### Recommended Next Phase

- `Phase N - Cost Path Reuse and Acceptance Capture`
- reason:
  - the current largest remaining hotspot is pricing/package evaluation
  - the app is now fast enough to be meaningfully interactive, so the next finish-line work is likely either:
    - targeted cost-path reuse optimization
    - or final acceptance/demo capture on the improved runtime

## Monday Lunch Selection Stall Diagnosis

### Status

PASS

### Root Cause

- The app was not hanging in startup.
- The visible stop at `Selection: Planning Monday lunch` was inside real first-slot selection.
- The main problem was `slow but still progressing`, caused by a very large Monday lunch main pool plus repeated waste inside main candidate evaluation.
- Two concrete waste sources were confirmed:
  - `_projected_day_calories()` repeatedly recomputed future-slot average calories by rescanning the dinner candidate pool for every Monday lunch main candidate.
  - `_select_recipe()` always ran `_best_choice()` twice for mains, even when the first repeat-capped pass had already found a valid winner.
- The app also lacked intra-slot updates, so that slow work looked like a stall.

### Files Inspected

- `pantry_pilot/planner.py`
- `pantry_pilot/app_runtime.py`
- `mvp/app.py`
- `tests/test_phaseM_performance_progress.py`
- `tests/test_phase6_regressions.py`

### Files Changed

- `pantry_pilot/planner.py`
- `pantry_pilot/selection_diagnosis.py`
- `tests/test_phaseN_monday_lunch_diagnosis.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
+ pantry_pilot/selection_diagnosis.py
+ reproducible Monday lunch benchmark / diagnosis command

~ pantry_pilot/planner.py
+ intra-slot progress updates during candidate batches
+ detailed selection timing breakdown support
+ cached future-slot average calorie projection
+ removed unconditional fallback `_best_choice()` rerun

+ tests/test_phaseN_monday_lunch_diagnosis.py
+ progress-batch and cache regression coverage
```

### Timing Breakdown For Monday Lunch

Verification command:

```powershell
& .\.venv\Scripts\python.exe -m pantry_pilot.selection_diagnosis --json
```

Real Monday lunch diagnosis after the fix:

- candidate gathering: `0.3444s`
- main candidates: `10,970`
- side candidates: `1,219`
- selected main: `Lentil Stew`
- selected side: `Mediterranean Caesar Salad`

Main timing:

- hard constraint filtering: `0.0213s`
- role gating: `0.1755s`
- main candidate ranking: `0.2204s`
- weekly balance scoring: `0.1474s`
- personal target scoring: `0.0209s`
- pantry/cost evaluation: `0.9011s`
- calorie projection: `0.7633s`
- total main selection: `3.4423s`

Side timing:

- hard constraint filtering: `0.0024s`
- role gating: `0.0014s`
- side candidate ranking: `0.0180s`
- weekly balance scoring: `0.0170s`
- personal target scoring: `0.0022s`
- pantry/cost evaluation: `0.1454s`
- calorie projection: `0.0480s`
- total side selection: `0.3206s`

Exact current hotspot:

- Monday lunch time is now spent mostly in:
  - pantry/cost evaluation
  - calorie projection
- Those are finite and progressing, not looping indefinitely.

### Before / After Timings

- before:
  - the real Monday lunch benchmark did not finish within a `120s` timeout
  - the app appeared frozen because progress only updated at the slot boundary
- after:
  - Monday lunch candidate gathering + main + side selection completes in about `4.11s`
  - main selection alone is `3.44s`
  - side selection is `0.32s`

### Intra-Slot Progress Behavior

- The app now receives progress updates while a slot is still being evaluated.
- Monday lunch now reports batch progress like:
  - `Main hard constraints: 100/10,970 candidates processed, 91 still viable.`
  - `Main hard constraints: 1,000/10,970 candidates processed, 866 still viable.`
  - `Main role gating: ...`
  - `Main ranking: ...`
- The progress bar also moves within the slot instead of waiting for the next slot boundary.

### Verification Command(s)

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phaseN_monday_lunch_diagnosis tests.test_phaseM_performance_progress
```

```powershell
& .\.venv\Scripts\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
& .\.venv\Scripts\python.exe -m pantry_pilot.selection_diagnosis --json
```

### Verification Result

- `tests.test_phaseN_monday_lunch_diagnosis tests.test_phaseM_performance_progress`
  - `Ran 5 tests`
  - `OK`
- `tests.test_phase6_regressions`
  - `Ran 8 tests in 49.662s`
  - `OK`
- diagnosis conclusion:
  - not a startup bug
  - not an infinite loop
  - real first-slot selection was too slow because of repeated waste on a pathological-but-finite candidate set
  - first slot now finishes in a reasonable time and shows visible intra-slot progress

### Recommended Next Phase

- `Phase N - Cost Path Reuse and Acceptance Capture`
- reason:
  - the largest remaining first-slot cost is still pantry/cost evaluation
  - now that the Monday lunch stall is diagnosed and fixed, the next targeted performance work should focus on cost-path reuse rather than selection architecture

## Phase O - Daily Nutrient State Engine

### Status

PASS

### Root Cause

- PantryPilot already had:
  - recipe-level nutrition
  - personal targets
  - calorie projection
  - week-level variety and balance scoring
- But the current planner still reasoned about target gaps mostly from:
  - whole-week meal history
  - slot-level calorie projection
  - component heuristics
- It did **not** maintain an explicit current-day nutrient state object while building the day.
- That meant:
  - side selection could not strongly react to what the current day already had
  - main/side pairs could still be redundant
  - diagnostics could explain reasons, but not the current day totals and remaining gaps

### Files Inspected

- `docs/recipe_planner_fix_plan.md`
- `docs/nutrition_data_plan.md`
- `docs/runtime_data_contract.md`
- `pantry_pilot/models.py`
- `pantry_pilot/planner.py`
- `pantry_pilot/nutrition.py`
- `pantry_pilot/personal_targets.py`
- `pantry_pilot/plan_display.py`
- `pantry_pilot/app_runtime.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase6_regressions.py`
- `tests/test_phaseG_planner_deliberation.py`
- `tests/test_phaseH_weekly_balance.py`
- `tests/test_phaseL_personal_targets.py`
- `tests/test_phaseN_monday_lunch_diagnosis.py`

### Files Changed

- `pantry_pilot/planner.py`
- `pantry_pilot/plan_display.py`
- `tests/test_phaseO_daily_nutrient_state.py`
- `docs/recipe_planner_fix_plan.md`

### Daily Nutrient State Model

- Added explicit planner dataclasses:
  - `DailyNutrientState`
  - `DailyNutrientDeficits`
- Tracked fields:
  - `calories`
  - `protein_grams`
  - `carbs_grams`
  - `fat_grams`
  - `produce_support`
  - `grains_starches_support`
  - `dairy_support`
- Planner behavior:
  - computes current day state from already-selected meals
  - computes projected day state after a candidate meal
  - computes remaining deficits against:
    - `request.personal_targets` when present
    - otherwise a deterministic manual-target layer derived from the request calorie range
- Diagnostics now expose:
  - `daily_state_before`
  - `daily_state_after`
  - `daily_deficits_before`
  - `daily_deficits_after`

### Planner Integration

- Main and side candidate scoring now use explicit daily deficit reduction:
  - protein gap closure
  - produce-support gap closure
  - grains/starches-support gap closure
  - dairy-support gap closure where applicable
  - calorie-gap improvement
- Side selection now has direct access to the post-main day state through the same diagnostic/scoring path.
- Preserved:
  - calorie enforcement
  - budget enforcement
  - allergen safety
  - honest unknown handling
  - pantry carryover
  - week-level balance logic
  - RecipeNLG runtime corpus

### Exact Diff

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
+from pantry_pilot.personal_targets import targets_from_manual_calorie_range
+@dataclass(frozen=True)
+class DailyNutrientState: ...
+@dataclass(frozen=True)
+class DailyNutrientDeficits: ...
+class MealSelectionDiagnostic(...):
+    daily_state_before: DailyNutrientState | None = None
+    daily_state_after: DailyNutrientState | None = None
+    daily_deficits_before: DailyNutrientDeficits | None = None
+    daily_deficits_after: DailyNutrientDeficits | None = None
+def current_day_nutrient_state(...): ...
+def day_nutrient_deficits(...): ...
+def _effective_daily_targets(...): ...
+def _meal_nutrient_state(...): ...
+def _current_day_state(...): ...
+def _projected_day_state(...): ...
+def _daily_nutrient_deficits(...): ...
+_evaluate_candidate(...)
+    daily_state_before = ...
+    daily_state_after = ...
+    daily_deficits_before = ...
+    daily_deficits_after = ...
+_personal_target_score(...)
+    # score main/side candidates by closing current-day deficits
+
diff --git a/pantry_pilot/plan_display.py b/pantry_pilot/plan_display.py
@@
+from pantry_pilot.planner import DailyNutrientDeficits, DailyNutrientState, MealSelectionDiagnostic
+def format_daily_nutrient_state(...): ...
+def format_daily_nutrient_deficits(...): ...
+build_plan_text_export(...)
+    Daily state before: ...
+    Daily state after: ...
+    Remaining deficits before: ...
+    Remaining deficits after: ...
+
diff --git a/tests/test_phaseO_daily_nutrient_state.py b/tests/test_phaseO_daily_nutrient_state.py
@@
+test_daily_nutrient_state_updates_after_adding_meals
+test_manual_and_profile_targets_produce_different_daily_deficits
+test_selection_diagnostics_expose_day_state_and_remaining_gaps_for_side_logic
```

### Verification Command(s)

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phaseO_daily_nutrient_state
```

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase2_app_display tests.test_phaseL_personal_targets tests.test_phaseG_planner_deliberation tests.test_phaseH_weekly_balance tests.test_phaseN_monday_lunch_diagnosis tests.test_phaseO_daily_nutrient_state
```

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions
```

### Worked Example

Controlled fixture:

- initial state before meal:
  - `0 cal | P 0.0g | C 0.0g | F 0.0g | produce 0.0 | grains/starches 0.0 | dairy 0.0`
- after adding `Chicken Plate`:
  - `280 cal | P 34.0g | C 4.0g | F 10.0g | produce 0.0 | grains/starches 0.0 | dairy 0.0`
- deficits before meal:
  - `2090 cal below minimum`
  - `protein 84.0g`
  - `carbs 252.0g`
  - `fat 49.8g`
  - `produce 5.0`
  - `grains/starches 7.0`
  - `dairy 3.0`
- deficits after main:
  - `1810 cal below minimum`
  - `protein 50.0g`
  - `carbs 248.0g`
  - `fat 39.8g`
  - `produce 5.0`
  - `grains/starches 7.0`
  - `dairy 3.0`

Later side-selection proof:

- selected pair:
  - `Chicken Plate:main`
  - `Broccoli Salad:side`
- side diagnostic before-state:
  - `280 cal | P 34.0g | C 4.0g | F 10.0g | produce 0.0 | grains/starches 0.0 | dairy 0.0`
- side diagnostic after-state:
  - `390 cal | P 37.0g | C 13.0g | F 17.0g | produce 1.8 | grains/starches 0.0 | dairy 0.0`
- side deficits improved:
  - produce support `5.0 -> 3.2`
- side reasoning contains:
  - `target:produce-gap`
- side runner-up:
  - `Lemon Rice`

### Before / After Behavior

Before:

- daily nutrition state existed only implicitly through recomputed meal history
- target scoring used weekly/slot heuristics more than current-day state
- diagnostics did not expose the current day totals or remaining deficits
- side logic could complement a main structurally, but not strongly enough through explicit current-day nutrient gaps

After:

- the planner maintains an explicit current-day nutrient state while constructing the day
- candidate scoring now rewards real daily deficit reduction
- the same current-day state is available to later side reasoning
- diagnostics and text exports expose the day state and remaining deficits before and after a selected meal

### Verification Result

- `tests.test_phaseO_daily_nutrient_state`
  - `Ran 3 tests in 0.015s`
  - `OK`
- `tests.test_phase2_app_display tests.test_phaseL_personal_targets tests.test_phaseG_planner_deliberation tests.test_phaseH_weekly_balance tests.test_phaseN_monday_lunch_diagnosis tests.test_phaseO_daily_nutrient_state`
  - `Ran 18 tests in 0.193s`
  - `OK`
- `tests.test_phase6_regressions`
  - `Ran 8 tests in 45.574s`
  - `OK`

### Recommended Next Phase

- `Phase P - Daily Pairing Acceptance And Gap-Driven Side Variety`
- reason:
  - the day-state engine now exists and is diagnostic-friendly
  - the next high-value step is acceptance coverage on contrasting daily meal pairs from the real RecipeNLG corpus, plus tighter use of gap-driven side variety on real-week outputs

## Phase P - Main-Side Complement With Daily Nutrient Awareness

### Status

PASS

### Root Cause

- PantryPilot already had:
  - side candidate pools
  - main/side component tagging
  - day-state nutrient deficits
  - weekly variety pressure
- But side choice still lacked an explicit composition profile for:
  - what the main already provides
  - what the side itself is dominated by
  - whether the pair is redundant or overly heavy
- The result was that side selection could still allow unrealistic pairings like:
  - starch-heavy main + starch-heavy side
  - produce-poor main + another non-produce side
  - heavy main + heavy redundant side

### Files Inspected

- `docs/recipe_planner_fix_plan.md`
- `docs/nutrition_data_plan.md`
- `docs/runtime_data_contract.md`
- `pantry_pilot/planner.py`
- `pantry_pilot/plan_display.py`
- `pantry_pilot/selection_diagnosis.py`
- `tests/test_phase2_app_display.py`
- `tests/test_phase6_regressions.py`
- `tests/test_phaseB_balance_scoring.py`
- `tests/test_phaseG_planner_deliberation.py`
- `tests/test_phaseH_weekly_balance.py`
- `tests/test_phaseL_personal_targets.py`
- `tests/test_phaseN_monday_lunch_diagnosis.py`
- `tests/test_phaseO_daily_nutrient_state.py`

### Files Changed

- `pantry_pilot/planner.py`
- `pantry_pilot/plan_display.py`
- `pantry_pilot/selection_diagnosis.py`
- `tests/test_phaseP_main_side_complement.py`
- `docs/recipe_planner_fix_plan.md`

### Complement Model

- Added explicit `MealCompositionProfile` with:
  - `protein_support`
  - `vegetable_support`
  - `starch_support`
  - `dairy_support`
  - `dominant_component`
  - `heaviness`
  - `density_score`
  - `components`
- Side scoring now combines:
  - main composition profile
  - side composition profile
  - current daily nutrient deficits
  - post-side daily nutrient deficits
  - existing weekly variety logic
- New complement behaviors:
  - rewards sides that fill a main produce gap
  - rewards sides that fill a main protein gap when daily protein is still missing
  - penalizes starch-heavy main + starch-heavy side
  - penalizes duplicate dominant components
  - penalizes heavy main + heavy side
  - keeps produce-poor non-produce sides penalized, but allows protein-forward sides to win once produce is mostly covered for the day
- Diagnostics now expose:
  - main composition profile
  - selected side composition profile
  - runner-up loss reasons

### Exact Diff

```diff
diff --git a/pantry_pilot/planner.py b/pantry_pilot/planner.py
@@
+@dataclass(frozen=True)
+class MealCompositionProfile:
+    protein_support: float
+    vegetable_support: float
+    starch_support: float
+    dairy_support: float
+    dominant_component: str
+    heaviness: str
+    density_score: float
+    components: frozenset[str]
@@
 class MealSelectionDiagnostic:
@@
+    anchor_composition_profile: MealCompositionProfile | None = None
+    selected_composition_profile: MealCompositionProfile | None = None
+    runner_up_loss_reasons: tuple[str, ...] = ()
@@
+def _meal_composition_profile(...): ...
+def _runner_up_loss_reasons(...): ...
@@
 _meal_balance_score(..., candidate_role=\"side\", anchor_recipe=...)
+    main_profile = self._meal_composition_profile(anchor_recipe, ...)
+    side_profile = self._meal_composition_profile(recipe, ...)
+    + complements-main-produce-gap
+    + complements-main-protein-gap
+    + complements-main-starch-gap
+    - penalty:starch-heavy-pairing
+    - penalty:duplicate-dominant-component
+    - penalty:produce-poor-pairing
+    - penalty:heavy-redundant-side
@@
 _personal_target_score(... candidate_role=\"side\" ...)
+    + target:protein-gap
+    + target:protein-priority

diff --git a/pantry_pilot/plan_display.py b/pantry_pilot/plan_display.py
@@
+def format_meal_composition_profile(...): ...
+build_plan_text_export(...)
+    Main composition: ...
+    Side composition: ...
+    Runner-up lost because: ...

diff --git a/tests/test_phaseP_main_side_complement.py b/tests/test_phaseP_main_side_complement.py
@@
+test_starch_heavy_main_avoids_redundant_starch_side_when_vegetable_side_exists
+test_same_main_gets_different_side_when_daily_deficits_change
+test_side_diagnostics_show_complement_and_runner_up_loss
```

### Verification Command(s)

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phaseP_main_side_complement
```

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase2_app_display tests.test_phaseB_balance_scoring tests.test_phaseG_planner_deliberation tests.test_phaseH_weekly_balance tests.test_phaseL_personal_targets tests.test_phaseN_monday_lunch_diagnosis tests.test_phaseO_daily_nutrient_state tests.test_phaseP_main_side_complement
```

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions
```

### Before / After Behavior

Before:

- a starch-heavy main could still pair with another redundant starch-heavy side
- side complement logic knew about generic missing components, but not explicit dominant-role redundancy or heaviness
- day-state target logic influenced sides, but not strongly enough to switch between produce-first and protein-first side choices for the same main
- diagnostics did not explicitly show why the runner-up side lost

After:

- starch-heavy mains are pushed away from redundant starch-heavy sides
- the planner now reasons about:
  - main dominant component
  - side dominant component
  - pair heaviness
  - day deficits before and after the side
- the same main can now produce different sides depending on remaining daily deficits
- diagnostics expose composition profiles and why a runner-up side lost

Controlled corrected pairing example:

- main:
  - `Creamy Pasta Plate`
- before correction risk:
  - `Creamy Pasta Plate + Lemon Rice`
- after planner fix:
  - selected side: `Broccoli Salad`
  - runner-up: `Egg Salad`
  - runner-up loss reasons include:
    - `runner-up-lost:weaker-main-side-complement`
    - `runner-up-lost:weaker-daily-target-fit`
    - `penalty:produce-poor-pairing`
- main composition:
  - dominant `starch`
  - `heavy`
- chosen side composition:
  - dominant `vegetable`
  - `light`
- daily produce deficit improved:
  - `5.0 -> 3.2`

Same-main different-deficit example:

- same dinner main:
  - `Creamy Pasta Plate`
- case A: no earlier produce coverage
  - selected side: `Broccoli Salad`
  - reason highlights:
    - `complements-main-produce-gap`
    - `target:produce-gap`
- case B: earlier lunch already covered most of the day’s produce
  - selected side: `Egg Salad`
  - runner-up: `Lemon Rice`
  - reason highlights:
    - `target:protein-gap`
    - `target:protein-priority`
  - protein deficit improved:
    - `70.4g -> 54.4g`

### Verification Result

- `tests.test_phaseP_main_side_complement`
  - `Ran 3 tests in 0.014s`
  - `OK`
- `tests.test_phase2_app_display tests.test_phaseB_balance_scoring tests.test_phaseG_planner_deliberation tests.test_phaseH_weekly_balance tests.test_phaseL_personal_targets tests.test_phaseN_monday_lunch_diagnosis tests.test_phaseO_daily_nutrient_state tests.test_phaseP_main_side_complement`
  - `Ran 24 tests in 0.235s`
  - `OK`
- `tests.test_phase6_regressions`
  - `Ran 8 tests in 54.634s`
  - `OK`

### Recommended Next Phase

- `Phase Q - Real RecipeNLG Pairing Acceptance`
- reason:
  - the complement model now exists and can switch sides based on day-state deficits
  - the next high-value step is acceptance validation on real weekly RecipeNLG outputs, including capture of corrected pairings and remaining edge cases in real corpus data

## Phase Q - Balanced Meal Acceptance Check

### Status

PASS

### Root Cause / Remaining Gap

- PantryPilot now has:
  - explicit daily nutrient state
  - main-side complement profiles
  - side diagnostics that explain gap-filling and runner-up loss
- The remaining question was no longer planner architecture. It was acceptance:
  - does the real runtime stack now produce more believable weekly pairings across contrasting scenarios?
- Real-stack acceptance showed clear pairing improvement signals:
  - zero selected starch+starch side pairings in all checked scenarios
  - real vegetable-side usage when produce gaps existed
  - real protein-gap support in the high-protein and carryover scenarios
- It also surfaced a remaining corpus-quality weak spot:
  - some RecipeNLG mains are still borderline or odd despite improved pairing behavior
  - that is now more clearly a `main-corpus / role-inference acceptance` issue than a `side complement` issue

### Files Inspected

- `docs/recipe_planner_fix_plan.md`
- `docs/nutrition_data_plan.md`
- `docs/runtime_data_contract.md`
- `pantry_pilot/acceptance.py`
- `pantry_pilot/app_runtime.py`
- `pantry_pilot/planner.py`
- `tests/test_phaseJ_acceptance.py`
- `tests/test_phase6_regressions.py`
- `tests/test_phaseP_main_side_complement.py`

### Files Changed

- `pantry_pilot/acceptance.py`
- `docs/recipe_planner_fix_plan.md`

### Exact Diff

```diff
diff --git a/pantry_pilot/acceptance.py b/pantry_pilot/acceptance.py
@@
-    scenario_id="tight_budget"
-    scenario_id="allergy_constrained"
+    scenario_id="high_protein_week"
+    scenario_id="tighter_calorie_week"
+    scenario_id="carryover_reuse"
@@
+from pantry_pilot.models import PlannerRequest, UserNutritionProfile
+from pantry_pilot.personal_targets import generate_personal_targets
@@
+def _high_protein_request(...): ...
+def _tighter_calorie_request(...): ...
+def _carryover_request(...): ...
+def _pairing_quality_summary(snapshot): ...
+def _merge_snapshot_details(snapshot): ...
@@
 _run_balanced_week(...)
+    pairing_quality = _pairing_quality_summary(snapshot)
+    require role-appropriate mains
+    require complementing sides
+    require zero starch-heavy selected pairings
+    require daily gap support
@@
+_run_high_protein_week(...)
+_run_tighter_calorie_week(...)
+_run_carryover_reuse(...)
```

### Acceptance Scenarios

- `balanced_week`
  - baseline real-stack balanced week
  - checks:
    - role-appropriate mains
    - complementing sides
    - zero selected starch+starch side pairings
    - produce-gap support visible
- `high_protein_week`
  - high-protein personal-target profile
  - checks:
    - role-appropriate mains
    - target-guided choices stay active
    - protein-gap support appears
    - redundant selected starch+starch side pairings remain zero
- `tighter_calorie_week`
  - lower-calorie profile week
  - checks:
    - role-appropriate mains
    - target-guided choices stay active
    - produce-gap support appears
    - redundant selected starch+starch side pairings remain zero
- `carryover_reuse`
  - two-run carryover scenario
  - checks:
    - pantry carryover actually reduces later purchases
    - second-week pairing quality still passes the balanced-pairing checks

### Verification Command(s)

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phaseJ_acceptance
```

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m pantry_pilot.acceptance --json
```

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase2_app_display tests.test_phaseB_balance_scoring tests.test_phaseG_planner_deliberation tests.test_phaseH_weekly_balance tests.test_phaseO_daily_nutrient_state tests.test_phaseP_main_side_complement tests.test_phaseJ_acceptance
```

### Results

Scenario outputs and pairing-quality summary:

- `Standard Balanced Week`
  - result: `PASS`
  - meals: `12`
  - mains: `7`
  - sides: `5`
  - pairing quality:
    - complementing sides: `2/5`
    - starch+starch selected pairings: `0`
    - produce-gap-supported sides: `5`
    - protein-gap-supported sides: `5`
    - target-guided choices: `12`
  - sample output:
    - `Chicken Roulade with Mixed Vegetables and Pan Fried Potatoes + Mediterranean Caesar Salad`
    - `French Toast Variation Of Eggs In A Basket + Zucchini And Eggs`

- `High-Protein Profile Week`
  - result: `PASS`
  - meals: `9`
  - mains: `7`
  - sides: `2`
  - pairing quality:
    - complementing sides: `1/2`
    - starch+starch selected pairings: `0`
    - produce-gap-supported sides: `2`
    - protein-gap-supported sides: `2`
    - target-guided choices: `9`
  - sample output:
    - `Easy Chicken Breast + Mediterranean Salad`
    - `Thai Cucumbers + Potato Soup Italian Style`

- `Tighter-Calorie Profile Week`
  - result: `PASS`
  - meals: `13`
  - mains: `7`
  - sides: `6`
  - pairing quality:
    - complementing sides: `5/6`
    - starch+starch selected pairings: `0`
    - produce-gap-supported sides: `6`
    - protein-gap-supported sides: `6`
    - target-guided choices: `13`
  - sample output:
    - `Nonnie'S Hot Dish + Mediterranean Caesar Salad`
    - `Greek Avgolemono Chicken Soup + Cucumbers With Dill`

- `Pantry Carryover Reuse Week`
  - result: `PASS`
  - week 1 cost: `$37.75`
  - week 2 cost with carryover: `$24.75`
  - baseline week 2 cost without carryover: `$37.75`
  - carryover used items: `9`
  - reduced purchase items: `8`
  - pairing quality on reused week:
    - complementing sides: `2/3`
    - starch+starch selected pairings: `0`
    - produce-gap-supported sides: `3`
    - protein-gap-supported sides: `3`
    - target-guided choices: `10`

Remaining weak spots from real runtime acceptance:

- some chosen mains are still not fully believable dinner anchors despite passing current role checks
- examples seen in acceptance output:
  - `Granny'S Baked Caramel Custard`
  - `Avocado Shake Recipe`
  - `Peanut Butter Sandwich With Sugar`
- this suggests the main-side pairing layer is materially better, but the remaining weakness is now:
  - main acceptance quality
  - corpus cleanup / stronger real-meal main gating

### Final Readiness For This Feature Area

- `READY WITH KNOWN LIMITATIONS`
- rationale:
  - balanced-pairing acceptance now passes on the real runtime stack
  - side complement behavior is measurably better
  - daily nutrient target support is visible in scenario metrics
  - redundant selected starch+starch pairings were eliminated in the checked scenarios
  - remaining issues are primarily on main acceptance realism, not side-complement logic

## Phase R - UI Polishing And Weekly Plan Readability

### Goal

- replace the overwhelming result long-scroll with a cleaner weekly planning interface
- keep planner output and planner logic intact
- show summary first, then progressively disclose meal detail and reasoning

### Implementation

- replaced the single long-scroll result section in the Streamlit app with four tabs:
  - `Weekly Plan`
  - `Shopping List`
  - `Pantry Carryover`
  - `Diagnostics / Planner Reasoning`
- added a compact weekly summary header for:
  - weekly shopping total
  - weekly nutrition summary
  - carryover used
  - plan balance summary
  - target summary
- changed the weekly plan area to per-day tabs so each day reads like a compact planner board instead of one long stacked page
- kept per-meal cards compact:
  - visible first:
    - meal name
    - main/side role
    - calories
    - consumed cost
    - added shopping cost
    - prep time
    - compact why-chosen summary
    - confidence label
  - hidden by default:
    - ingredients and steps
    - daily nutrient state and deficits
    - main/side composition details
    - runner-up loss reasons
- grouped shopping items into practical grocery sections for easier scanning while preserving:
  - amount needed
  - carryover used
  - amount being bought
  - leftover after plan
  - package count
  - estimated cost
  - price source

### Verification Command(s)

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase2_app_display
```

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phaseI_ui_reliability tests.test_phase2_app_display tests.test_phaseJ_acceptance
```

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase6_regressions
```

### Results

- page structure before:
  - planner notes
  - budget and calorie summary
  - export controls
  - all seven days stacked vertically
  - full shopping list table at the bottom
- page structure after:
  - compact weekly summary header
  - separate tabs for weekly plan, shopping, carryover, and diagnostics
  - per-day tabs inside the weekly plan
  - detailed rationale and nutrition state hidden behind expanders
- long-scroll reduction:
  - the default result view now lands on summary cards plus one top-level tab row instead of immediately showing every meal, every ingredient list, and the full shopping table in one page flow
- render-safety coverage:
  - added tests for per-day summary view-model generation
  - added tests for grouped shopping-list display sections
  - existing export/render helper tests still pass

### Status

- `PASS`

### Recommended Next Phase

- Phase S: main-meal realism and stronger RecipeNLG anchor acceptance on the weekly UI, using the cleaner diagnostics tab to surface weak-anchor mains without overwhelming the default plan view

## Phase T - Repository Cleanup And Submission Organization

### Goal

- clean the repo so the submission path is obvious
- make PantryPilot the clear main project
- reduce clutter from local caches, build artifacts, and stale documentation structure

### Implementation

- added a submission-facing `phase2/` folder with markdown report and index
- added repo index files for:
  - `proposal/`
  - `docs/`
  - `phase2/`
- replaced the top-level `README.md` with a current PantryPilot-focused overview and repo map
- converted the old extensionless proposal report into markdown:
  - `proposal/proposal2` -> `proposal/project_report.md`
- tightened `.gitignore` for:
  - USDA raw snapshot inputs
  - local nutrition build caches
  - RecipeNLG raw source dumps
  - processed checkpoint and log artifacts
  - pantry carryover state
  - saved plans state
  - local cache and machine-specific folders
  - temporary scratch diff files
- removed obvious local clutter from the working tree:
  - `hf_cache/`
  - `mvp/__pycache__/`
  - top-level scratch `*.diff` files

### Submission-Facing Repo Structure

- `proposal/`
- `phase2/`
- `mvp/`
- `docs/`
- `pantry_pilot/`
- `tests/`

### Verification Command(s)

```powershell
Get-ChildItem | Select-Object Mode,Name
```

```powershell
git status --short
```

```powershell
& C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_phase2_app_display tests.test_phaseJ_acceptance
```

### Results

- before:
  - repo root mixed submission folders with local cache/scratch items
  - no `phase2/` submission landing area
  - proposal report used an extensionless file
  - top-level README still emphasized earlier milestone framing
- after:
  - repo root now has clear submission-facing folders
  - `phase2/` exists and points a grader to the current markdown report
  - proposal materials are indexed and markdown-based
  - README now centers PantryPilot and gives a direct repo map
  - ignore rules now treat raw snapshots, local build artifacts, carryover state, and machine-specific files as non-submission content

### Status

- `PASS`

### Recommended Next Phase

- Phase U: main-meal realism hardening and final submission branch packaging, focused on reducing weak-anchor mains while keeping the cleaned repo structure stable
