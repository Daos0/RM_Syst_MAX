from app.api.normalization import normalize_name
from app.db.seed import catalog_seed_data
from app.db.seed_data import ALIASES, TEMPLATES


def test_name_normalization_is_shared_and_stable() -> None:
    assert normalize_name("  Ёлка   и   мёд ") == "елка и мед"


def test_catalog_bootstrap_has_no_duplicates_or_broken_references() -> None:
    data = catalog_seed_data()
    categories = data["categories"]
    products = data["products"]
    recipes = data["recipes"]

    category_codes = [item["code"] for item in categories]
    category_orders = [(item["kind"], item["sort_order"]) for item in categories]
    product_names = [item["normalized_name"] for item in products]
    recipe_codes = [item["code"] for item in recipes]
    recipe_names = [item["normalized_name"] for item in recipes]

    assert len(category_codes) == len(set(category_codes))
    assert len(category_orders) == len(set(category_orders))
    assert len(product_names) == len(set(product_names))
    assert len(recipe_codes) == len(set(recipe_codes))
    assert len(recipe_names) == len(set(recipe_names))

    category_code_set = set(category_codes)
    product_name_set = set(product_names)
    assert all(item["category_code"] is None or item["category_code"] in category_code_set for item in products)
    assert all(item["category_code"] in category_code_set for item in recipes)
    assert set(ALIASES) <= product_name_set
    assert {name for _, _, names in TEMPLATES.values() for name in names} <= product_name_set

    for recipe in recipes:
        variant_codes = [variant["code"] for variant in recipe["variants"]]
        assert len(variant_codes) == len(set(variant_codes))
        for variant in recipe["variants"]:
            ingredient_names = [item["product_normalized_name"] for item in variant["ingredients"]]
            assert len(ingredient_names) == len(set(ingredient_names))
            assert set(ingredient_names) <= product_name_set
            assert len(ingredient_names) >= 3
            assert all(item["quantity"] > 0 for item in variant["ingredients"])
            ingredient_orders = [item["sort_order"] for item in variant["ingredients"]]
            assert ingredient_orders == list(range(1, len(ingredient_orders) + 1))


def test_dish_categories_are_balanced_for_two_column_layout() -> None:
    recipes = catalog_seed_data()["recipes"]
    dish_counts: dict[str, int] = {}
    for recipe in recipes:
        dish_counts[recipe["category_code"]] = dish_counts.get(recipe["category_code"], 0) + 1

    assert len(dish_counts) == 8
    assert set(dish_counts.values()) == {12}


def test_known_recipe_content_errors_do_not_return() -> None:
    recipes = {item["code"]: item for item in catalog_seed_data()["recipes"]}

    def ingredients(code: str) -> set[str]:
        return {
            item["product_normalized_name"]
            for variant in recipes[code]["variants"]
            for item in variant["ingredients"]
        }

    assert "перловая крупа" in ingredients("rassolnik")
    assert "рис" not in ingredients("rassolnik")
    assert {"салат романо", "соус цезарь"} <= ingredients("caesar-chicken")
    assert {"чеснок", "грецкие орехи", "соус ткемали"} <= ingredients("kharcho")
    assert "мед" in ingredients("honey-cake")
    assert "баклажаны" in ingredients("ratatouille")
    assert "огурцы" not in ingredients("grilled-vegetables")
