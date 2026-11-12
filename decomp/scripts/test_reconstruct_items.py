"""Run with DATA.BIN, the matching ISO, and the mhfu-db checkout as arguments."""

from pathlib import Path
import sys
import unittest

import reconstruct_items as extraction


class ReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        boot = extraction.read_boot(iso)
        cls.entry, cls.items = extraction.read_game_items(archive, boot)
        cls.recipes = extraction.read_recipes(boot, cls.items)
        cls.public_items, _ = extraction.read_public(repo / "items.json", extraction.ITEM_KEYS)
        cls.public_recipes, _ = extraction.read_public(repo / "items-combine.json", extraction.RECIPE_KEYS)

    def test_item_ids_and_values(self):
        self.assertEqual(self.entry, 19)
        self.assertEqual([item["id"] for item in self.items], list(range(1261)))
        potion = extraction.public_item(self.items[7])
        self.assertEqual((potion["name"], potion["rare"], potion["carry-max"], potion["selling-price"]),
                         ("Potion", 1, 10, 7))
        self.assertEqual(extraction.public_item(self.items[65])["carry-max"], 5)
        self.assertEqual(extraction.public_item(self.items[96])["carry-max"], "Infinity")

    def test_item_schema_and_accounting(self):
        generated, report = extraction.compare_items(self.public_items, self.items)
        extraction.check_output_types(self.public_items, generated, extraction.ITEM_KEYS, ("id",))
        self.assertEqual(len(generated), len({row["id"] for row in generated}))
        self.assertEqual(report["published_rows"], report["linked_rows"] + len(report["unresolved_published_rows"]))
        self.assertEqual(len(generated) + len(report["placeholder_ids"]), len(self.items))
        self.assertEqual([row["id"] for row in report["new_english_records"]], [128, 875])
        self.assertFalse(report["replacement_ready"])

    def test_schema_guard_rejects_bool_for_number(self):
        with self.assertRaises(ValueError):
            extraction.check_schema({"rare": 1}, {"rare": True})

    def test_item_patch_preserves_unresolved_rows(self):
        generated, report = extraction.compare_items(self.public_items, self.items)
        operations = extraction.item_patch(self.public_items, generated, report)
        applied = list(self.public_items)
        for operation in operations:
            index = int(operation["path"][1:])
            if operation["op"] == "test":
                self.assertEqual(applied[index], operation["value"])
            else:
                extraction.check_schema(applied[index], operation["value"], ("id",))
                applied[index] = operation["value"]
        self.assertEqual(len(applied), len(self.public_items))
        self.assertEqual(sum("id" in row for row in applied), report["linked_rows"])
        for unresolved in report["unresolved_published_rows"]:
            self.assertEqual(applied[unresolved["published_row"]], unresolved["published"])

    def test_recipe_candidate_preserves_schema_order_and_material_links(self):
        generated, report = extraction.compare_recipes(self.public_recipes, self.recipes, self.items)
        self.assertEqual(len(generated), 172)
        self.assertTrue(report["replacement_ready"])
        self.assertEqual(generated, self.public_recipes)
        self.assertEqual({recipe["recipe_id"] for recipe in self.recipes}, set(range(172)))
        first = self.recipes[0]
        self.assertEqual((first["material_ids"], first["result_item_id"], first["base_chance"]), ([163, 177], 7, 95))
        named_items, _ = extraction.compare_items(self.public_items, self.items)
        named_ids = {row["id"] for row in named_items}
        for recipe in self.recipes:
            self.assertTrue(named_ids.issuperset(recipe["material_ids"] + [recipe["result_item_id"]]))
            self.assertEqual(sum(recipe["quantity"]["weights"]), 100)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(f"Usage: {sys.argv[0]} DATA.BIN game.iso mhfu-db")
    archive, iso, repo = map(Path, sys.argv[1:])
    unittest.main(argv=[sys.argv[0]])
