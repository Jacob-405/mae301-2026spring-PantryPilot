import tempfile
import unittest
from pathlib import Path

from pantry_pilot.data_pipeline.importer import ImportConfig, import_kaggle_recipe_directory


class Phase12KaggleImportTests(unittest.TestCase):
    def test_kaggle_directory_import_accepts_structured_test_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "recipes.csv").write_text(
                ",".join(["", "recipe_name", "prep_time", "cook_time", "total_time", "servings", "yield", "ingredients", "directions", "rating", "url", "cuisine_path", "nutrition", "timing", "img_src"])
                + "\n",
                encoding="utf-8",
            )
            (base / "test_recipes.csv").write_text(
                "\n".join(
                    [
                        "Row,Name,Prep Time,Cook Time,Total Time,Servings,Yield,Ingredients,Directions,url,Additional Time",
                        '0,"Vegetable Rice Bowl",20 mins,20 mins,40 mins,6,,"[{""quantity"": ""2"", ""unit"": ""cups"", ""name"": ""white rice""}, {""quantity"": ""1"", ""unit"": ""tablespoon"", ""name"": ""minced garlic""}, {""quantity"": ""1"", ""unit"": ""cup"", ""name"": ""chopped onion""}, {""quantity"": ""2"", ""unit"": ""item"", ""name"": ""tomatoes""}]","[""Cook rice."", ""Cook onion and garlic."", ""Top with tomatoes.""]","https://example.com",',
                    ]
                ),
                encoding="utf-8",
            )

            result = import_kaggle_recipe_directory(base, config=ImportConfig(max_unmapped_ingredient_fraction=0.0))

            self.assertEqual(len(result.imported_recipes), 1)
            self.assertEqual(result.imported_recipes[0].title, "Vegetable Rice Bowl")

    def test_kaggle_free_text_dessert_rows_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "recipes.csv").write_text(
                "\n".join(
                    [
                        ',recipe_name,prep_time,cook_time,total_time,servings,yield,ingredients,directions,rating,url,cuisine_path,nutrition,timing,img_src',
                        '0,Apple Pie,30 mins,1 hrs,1 hrs 30 mins,8,,"8 apples, 1 cup sugar, 1 pie crust","Bake pie.",4.8,https://example.com,/Desserts/Pies/Apple Pie Recipes/,"",,',
                    ]
                ),
                encoding="utf-8",
            )
            (base / "test_recipes.csv").write_text(
                "Row,Name,Prep Time,Cook Time,Total Time,Servings,Yield,Ingredients,Directions,url,Additional Time\n",
                encoding="utf-8",
            )

            result = import_kaggle_recipe_directory(base)

            self.assertEqual(result.imported_recipes, ())
            self.assertEqual(result.stats["rejected_count"], 1)
            self.assertTrue(any("Meal type could not be mapped" in item["reason"] for item in result.stats["common_reject_reasons"]))


if __name__ == "__main__":
    unittest.main()
