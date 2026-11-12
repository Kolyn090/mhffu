"""Reconstruct English item and recipe records from DATA.BIN and the matching disc."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct

from audit_database import EN_SHA256, read_item_texts, unique_keys
from decode_mhfu import SECTOR_BYTES, read_entry_data, read_exact, read_index


# North American ULUS10391 v1.01. BOOT.BIN is the clear ELF on the same disc.
BOOT_SECTOR = 54704
BOOT_BYTES = 1910332
BOOT_SHA256 = "3070954e2dc88fd0b0836c0c1dc526531aca4a213b0f18806e324963efb514f4"
LOAD_DELTA = 0x08801A4C
ITEM_TABLE = 0x19B86C
MIX_TABLE = 0x1A2EA4
MIX_INDEX = 0x1A355C
MIX_BOOK = 0x1A3F38
MIX_QUANTITY_POINTERS = 0x1A4208
MIX_MAX = 0x1A4224
MIX_RATES = 0x1A422C
GAME_SUB_ENTRY = 76
GAME_SUB_BASE = 0x09C19100
RARITY_LOAD = 0x09C2B2CC
RARITY_INCREMENT = 0x09C2B2D8
ITEM_COUNT = 1261
MIX_COUNT = 172
ITEM = struct.Struct("<7BxHHIIHH")
MIX = struct.Struct("<HHbBBBBx")
PAIR = struct.Struct("<HH")
ITEM_KEYS = ("name", "rare", "description", "carry-max", "icon", "color", "selling-price")
RECIPE_KEYS = ("name", "type", "materialA", "materialB", "chance", "min", "max")

# Public presentation tokens for the executable's icon sprite and palette IDs.
ICONS = dict(enumerate((
    "smoke", "ball", "bomb", "meat", "bait", "fish", "tool", "whetstone", "dung",
    "monster", "bone", "binoculars", "mushroom", "bugnet", "pelt", "herb", "pickaxe",
    "barrel", "seed", "bbq-spit", "insect", "trap", "web", "scale", "bottle", "egg",
    "shell", "ore", "husk", "map", "flute", "fang", "honey", "unknown", "coin", "bag",
    "book", "ticket", "knife",
)))
ICONS.update({
    43: "jewel", 49: "boomerang", 50: "bottle", 51: "empty-bottle",
    52: "carapaceon-shell", 54: "hvnly-scale", 55: "armor-stone",
})
COLORS = dict(enumerate(("white", "red", "green", "blue", "yellow", "purple", "sky", "orange", "pink")))
COLORS[10] = "gray"


def read_boot(iso):
    with iso.open("rb") as disc:
        disc.seek(BOOT_SECTOR * SECTOR_BYTES)
        data = read_exact(disc, BOOT_BYTES)
    if hashlib.sha256(data).hexdigest() != BOOT_SHA256:
        raise ValueError("BOOT.BIN differs from the verified ULUS10391 v1.01 disc executable")
    return data


def read_game_items(archive, boot):
    with archive.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != EN_SHA256:
            raise ValueError("DATA.BIN differs from the verified ULUS10391 v1.01 archive")
        source.seek(0)
        entries = read_index(source)
        entry, strings = read_item_texts(source, entries)
        pack = read_entry_data(source, entries[entry])
        verify_rarity_display(source, entries[GAME_SUB_ENTRY])
    if len(strings) != ITEM_COUNT or ITEM_TABLE + len(strings) * ITEM.size != MIX_TABLE:
        raise ValueError("Item definition and localization counts disagree")
    names, descriptions = struct.unpack_from("<II", pack, 12)
    keys = (
        "item_type", "toolbelt_flags", "raw_rarity", "stack_size", "flags", "icon_id",
        "color_id", "ammo_bits", "pickup_sound", "buy_value", "sell_value",
        "unused", "decoration_id",
    )
    items = []
    for text in strings:
        item_id = text["id"]
        offset = ITEM_TABLE + item_id * ITEM.size
        values = ITEM.unpack_from(boot, offset)
        name_pointer, = struct.unpack_from("<I", pack, names + item_id * 4)
        description_pointer, = struct.unpack_from("<I", pack, descriptions + item_id * 4)
        items.append({
            **text, "definition_offset": offset, "name_offset": names + name_pointer,
            "description_offset": descriptions + description_pointer, **dict(zip(keys, values)),
        })
    return entry, items


def verify_rarity_display(source, entry):
    load = 64 + RARITY_LOAD - GAME_SUB_BASE
    increment = 64 + RARITY_INCREMENT - GAME_SUB_BASE
    overlay = read_entry_data(source, entry, increment + 4)
    # lbu v1, 2(s0) followed by addiu t0, v1, 1 before the display call.
    if (overlay[:4] != b"MWo3" or overlay[32:64].split(b"\0")[0] != b"game_sub.ovl"
            or struct.unpack_from("<I", overlay, 8)[0] != GAME_SUB_BASE
            or struct.unpack_from("<I", overlay, load)[0] != 0x92030002
            or struct.unpack_from("<I", overlay, increment)[0] != 0x24680001):
        raise ValueError("English rarity display routine did not match the expected instruction sequence")


def single_line(value):
    return " ".join(re.sub(r"-[ \t]*\r?\n[ \t]*", "-", value).split())


def public_item(item):
    return {
        "name": single_line(item["name"]),
        "rare": item["raw_rarity"] + 1,
        "description": single_line(item["description"]),
        "carry-max": "Infinity" if item["stack_size"] == 0xFF else item["stack_size"],
        "icon": ICONS[item["icon_id"]],
        "color": COLORS[item["color_id"]],
        "selling-price": item["sell_value"],
        "id": item["id"],
    }


def read_quantities(boot):
    quantities = []
    for index, maximum in enumerate(boot[MIX_MAX:MIX_MAX + 7]):
        pointer, = struct.unpack_from("<I", boot, MIX_QUANTITY_POINTERS + 4 * index)
        offset = pointer - LOAD_DELTA
        if not 0 <= offset < len(boot):
            raise ValueError(f"Invalid recipe quantity pointer {pointer:#x}")
        minimum = boot[offset]
        weights = list(boot[offset + 1:offset + 2 + maximum - minimum])
        if not 1 <= minimum <= maximum or sum(weights) != 100 or any(weight == 0 for weight in weights):
            raise ValueError(f"Invalid quantity distribution at {offset:#x}")
        quantities.append({"min": minimum, "max": maximum, "weights": weights, "offset": offset})
    return quantities


def read_recipes(boot, items):
    rates = boot[MIX_RATES:MIX_RATES + 7]
    quantities = read_quantities(boot)
    indexed = {}
    by_pair = {}
    for first in range(ITEM_COUNT):
        count, start = struct.unpack_from("<BB", boot, MIX_INDEX + first * 2)
        if start + count > MIX_COUNT:
            raise ValueError(f"Invalid recipe index at item {first}")
        for row in range(start, start + count):
            offset = MIX_TABLE + row * MIX.size
            second, result, rate, quantity, recipe_id, flags, alternate_index = MIX.unpack_from(boot, offset)
            pair = (first, second)
            if (recipe_id != row or row in indexed or pair in by_pair or not 0 < first <= second < len(items)
                    or not 0 < result < len(items) or not 0 <= rate < len(rates)
                    or quantity >= len(quantities) or flags & ~0x1F):
                raise ValueError(f"Invalid recipe definition at {offset:#x}")
            indexed[row] = pair
            by_pair[pair] = {
                "recipe_id": recipe_id, "definition_offset": offset,
                "result_item_id": result, "base_chance": rates[rate], "rate_id": rate,
                "quantity_id": quantity, "quantity": quantities[quantity],
                "flags": flags, "alternate_index": alternate_index,
            }
    if len(indexed) != MIX_COUNT or PAIR.unpack_from(boot, MIX_BOOK + MIX_COUNT * PAIR.size) != (65535, 65535):
        raise ValueError("Recipe index coverage or combination list terminator is invalid")

    recipes = []
    used = set()
    for order in range(MIX_COUNT):
        first, second = PAIR.unpack_from(boot, MIX_BOOK + order * PAIR.size)
        pair = tuple(sorted((first, second)))
        if pair not in by_pair or pair in used:
            raise ValueError(f"Combination list has an invalid ingredient pair at row {order}")
        recipe = by_pair[pair]
        flags = recipe["flags"]
        # The seven assembled treasure records have both reveal flags and a treasure result.
        if flags & 0x0C == 0x0C and not items[recipe["result_item_id"]]["flags"] & 0x10:
            raise ValueError(f"Treasure combination has a non-treasure result at row {order}")
        recipes.append({
            "book_index": order, "material_ids": [first, second], **recipe,
            "type": "alchemy" if flags & 1 else "treasure" if flags & 0x0C == 0x0C else "normal",
        })
        used.add(pair)
    return recipes


def public_recipe(recipe, items):
    first, second = recipe["material_ids"]
    return {
        "name": single_line(items[recipe["result_item_id"]]["name"]),
        "type": recipe["type"],
        "materialA": single_line(items[first]["name"]),
        "materialB": single_line(items[second]["name"]),
        "chance": recipe["base_chance"],
        "min": recipe["quantity"]["min"],
        "max": recipe["quantity"]["max"],
    }


def check_schema(before, after, allowed_added=()):
    """Check both key order and field types for every replaced public row."""
    if tuple(key for key in after if key not in allowed_added) != tuple(before):
        raise ValueError("Public fields were added, removed, reordered, or renamed")
    for key in before:
        if type(before[key]) is not type(after[key]):
            raise ValueError(f"Type changed for {key!r}")


def changes(before, after):
    return {key: {"old": before.get(key), "generated": value}
            for key, value in after.items() if before.get(key) != value}


def item_signature(row):
    return single_line(row["name"]), single_line(row["description"]), tuple(
        (type(row[key]), row[key]) for key in ITEM_KEYS if key not in {"name", "description"}
    )


def compare_items(original, items):
    placeholders = [item["id"] for item in items if item["id"] == 0 or
                    (item["name"] == "dummy" and item["description"] == "dummy")]
    generated = {item["id"]: public_item(item) for item in items if item["id"] not in placeholders}
    by_name = defaultdict(list)
    for row in generated.values():
        by_name[row["name"]].append(row)
    old_names = Counter(single_line(row["name"]) for row in original)
    old_signatures = Counter(item_signature(row) for row in original)
    ordered, corrections, unresolved, matched_ids = [], [], [], set()
    for index, row in enumerate(original):
        name = single_line(row["name"])
        candidates = by_name.get(name, [])
        matches = [value for value in candidates if value["description"] == single_line(row["description"])]
        duplicate_name = old_names[name] != 1
        evidence = "Unique English name and description after joining display lines"
        if duplicate_name:
            signature = item_signature(row)
            matches = [
                value for value in matches if item_signature(value) == signature and old_signatures[signature] == 1
            ]
            evidence = "Only duplicate row whose full public record agrees with the English definition and text"
        if len(matches) != 1:
            unresolved.append({
                "published_row": index, "published": row,
                "candidate_ids": [value["id"] for value in candidates],
                "reason": "duplicate published name" if duplicate_name else
                "description has no unique match" if candidates else "no matching English name",
            })
            continue
        new = matches[0]
        check_schema(row, new, ("id",))
        if new["id"] in matched_ids:
            raise ValueError(f"Item ID {new['id']} was linked to multiple rows")
        ordered.append(new)
        matched_ids.add(new["id"])
        corrections.append({
            "published_row": index, "id": new["id"], "name": new["name"],
            "evidence": evidence,
            "changes": changes(row, new),
        })
    ambiguous_ids = {item_id for row in unresolved for item_id in row["candidate_ids"]}
    unlinked = [value for item_id, value in generated.items() if item_id not in matched_ids]
    new_records = [value for value in unlinked if value["id"] not in ambiguous_ids]
    return ordered + unlinked, {
        "published_rows": len(original), "linked_rows": len(matched_ids),
        "generated_named_item_records": len(generated), "placeholder_ids": placeholders,
        "changed_fields": dict(Counter(field for row in corrections for field in row["changes"])),
        "corrections": corrections, "unresolved_published_rows": unresolved,
        "english_ids_claimed_by_unresolved_rows": sorted(ambiguous_ids),
        "new_english_records": new_records,
        "replacement_ready": not unresolved,
    }


def recipe_key(row):
    return tuple(sorted(single_line(row[key]) for key in ("materialA", "materialB")))


def item_patch(original, generated, report):
    """Build a guarded JSON Patch for linked rows only."""
    by_id = {row["id"]: row for row in generated}
    tests, replacements = [], []
    for link in report["corrections"]:
        index = link["published_row"]
        path = f"/{index}"
        tests.append({"op": "test", "path": path, "value": original[index]})
        replacements.append({"op": "replace", "path": path, "value": by_id[link["id"]]})
    return tests + replacements


def compare_recipes(original, recipes, items):
    indexed = {recipe_key(public_recipe(recipe, items)): recipe for recipe in recipes}
    if len(indexed) != len(recipes):
        raise ValueError("Localized ingredient pairs collide")
    ordered, corrections, unresolved, used = [], [], [], set()
    old_pairs = Counter(recipe_key(row) for row in original)
    for index, row in enumerate(original):
        key = recipe_key(row)
        recipe = indexed.get(key)
        if recipe is None or old_pairs[key] != 1:
            unresolved.append({"published_row": index, "published": row})
            continue
        new = public_recipe(recipe, items)
        check_schema(row, new)
        ordered.append(new)
        used.add(key)
        difference = changes(row, new)
        if difference:
            corrections.append({"published_row": index, "recipe_id": recipe["recipe_id"], "changes": difference})
    added = [public_recipe(recipe, items) for key, recipe in indexed.items() if key not in used]
    return ordered + added, {
        "published_rows": len(original), "linked_rows": len(used), "game_recipes": len(recipes),
        "changed_fields": dict(Counter(field for row in corrections for field in row["changes"])),
        "corrections": corrections, "unresolved_published_rows": unresolved,
        "unlinked_game_recipes": added, "replacement_ready": not unresolved,
    }


def source_map(string_entry):
    return {
        "release": "ULUS10391 v1.01",
        "data_bin_sha256": EN_SHA256,
        "boot_bin": {
            "path_on_disc": "/PSP_GAME/SYSDIR/BOOT.BIN", "iso_first_sector": BOOT_SECTOR,
            "bytes": BOOT_BYTES, "sha256": BOOT_SHA256,
            "file_to_load_address_delta": LOAD_DELTA,
        },
        "items.json": {
            "id": {"status": "stored indexing", "source": "Shared zero-based slot in item and text tables"},
            "name": {"status": "extracted", "entry": string_entry, "group": 1, "transform": "Join display lines"},
            "description": {"status": "extracted", "entry": string_entry, "group": 2,
                            "transform": "Join display lines, preserving hyphens and game control codes"},
            "definition_table": {"source": "BOOT.BIN", "offset": ITEM_TABLE, "stride": ITEM.size, "count": ITEM_COUNT},
            "rare": {
                "status": "derived", "record_offset": 2, "type": "u8",
                "transform": "Add one to zero-based rank as done by the English item display routine",
                "display_code": {"entry": GAME_SUB_ENTRY, "load_address": RARITY_LOAD, "increment_address": RARITY_INCREMENT},
            },
            "carry-max": {"status": "derived", "record_offset": 3, "type": "u8", "transform": "0xff unlimited sentinel renders as Infinity"},
            "icon": {"status": "presentation", "record_offset": 5, "type": "u8", "labels": ICONS},
            "color": {"status": "presentation", "record_offset": 6, "type": "u8", "labels": COLORS},
            "selling-price": {"status": "extracted", "record_offset": 16, "type": "u32le", "unit": "zenny"},
        },
        "items-combine.json": {
            "definition_table": {"source": "BOOT.BIN", "offset": MIX_TABLE, "stride": MIX.size, "count": MIX_COUNT},
            "material_index": {"offset": MIX_INDEX, "stride": 2, "count": ITEM_COUNT, "fields": ["count", "first_definition"]},
            "combination_book": {"offset": MIX_BOOK, "stride": PAIR.size, "count": MIX_COUNT, "sentinel": [65535, 65535]},
            "name": {"status": "derived", "record_offset": 2, "transform": "Look up result item ID in English name table"},
            "materialA": {"status": "derived", "transform": "First book ingredient ID resolved through English item names"},
            "materialB": {"status": "derived", "transform": "Second book ingredient ID resolved through English item names"},
            "type": {"status": "derived", "record_offset": 7, "transform": "Alchemy flag bit 0. Treasure uses both reveal bits (2 and 3) and a treasure result. Other recipes are normal."},
            "chance": {"status": "derived", "record_offset": 4, "lookup_offset": MIX_RATES, "unit": "base percent before bonuses"},
            "min": {"status": "derived", "record_offset": 5, "quantity_pointer_table": MIX_QUANTITY_POINTERS},
            "max": {"status": "derived", "record_offset": 5, "quantity_max_table": MIX_MAX},
        },
    }


def read_public(path, keys):
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_keys)
    if not isinstance(data, list) or any(not isinstance(row, dict) or tuple(row) != keys for row in data):
        raise ValueError(f"Unexpected repository schema in {path}")
    return data, hashlib.sha256(raw).hexdigest()


def check_output_types(original, generated, fields, added=()):
    allowed = {key: {type(row[key]) for row in original} for key in fields}
    for row in generated:
        if tuple(row) != fields + added or any(type(row[key]) not in allowed[key] for key in fields):
            raise ValueError("Generated row is outside the public JSON schema")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("iso", type=Path, help="Original North American ISO containing the matching BOOT.BIN")
    parser.add_argument("repository", type=Path)
    parser.add_argument("output", type=Path, help="New output directory outside the repository")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(args.repository.resolve()):
        parser.error("Output must be a new directory outside the repository")

    original_items, item_hash = read_public(args.repository / "items.json", ITEM_KEYS)
    original_recipes, recipe_hash = read_public(args.repository / "items-combine.json", RECIPE_KEYS)
    boot = read_boot(args.iso)
    string_entry, items = read_game_items(args.archive, boot)
    generated_items, item_report = compare_items(original_items, items)
    recipes = read_recipes(boot, items)
    generated_recipes, recipe_report = compare_recipes(original_recipes, recipes, items)
    check_output_types(original_items, generated_items, ITEM_KEYS, ("id",))
    check_output_types(original_recipes, generated_recipes, RECIPE_KEYS)
    output.mkdir(parents=True)
    write_json(output / "source-map.json", source_map(string_entry))
    write_json(output / "raw" / "item-definitions.json", items)
    write_json(output / "raw" / "mix-definitions.json", recipes)
    write_json(output / "item-changes.json", {"published_sha256": item_hash, **item_report})
    write_json(output / "item-updates.patch.json", item_patch(original_items, generated_items, item_report))
    write_json(output / "recipe-changes.json", {"published_sha256": recipe_hash, **recipe_report})
    item_dir = "candidates" if item_report["replacement_ready"] else "generated"
    recipe_dir = "candidates" if recipe_report["replacement_ready"] else "generated"
    write_json(output / item_dir / "items.json", generated_items)
    write_json(output / recipe_dir / "items-combine.json", generated_recipes)
    print(f"Generated {len(generated_items)} items and {len(generated_recipes)} recipes")
    print(f"Replacement-ready: items={item_report['replacement_ready']}, recipes={recipe_report['replacement_ready']}")


if __name__ == "__main__":
    main()
