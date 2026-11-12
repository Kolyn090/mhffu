"""Inventory mhfu-db and compare selected fields with the original English DATA.BIN."""

import argparse
from collections import Counter, defaultdict
from hashlib import file_digest, sha256
import json
from pathlib import Path

from decode_mhfu import decode_quest, read_entry_data, read_index
from extract_gathering import find_english_item_names, u16, u32


EN_SHA256 = "d7e5b5cebe07fe00ae1167ed6779f8a6d246ffe35842878a1aeadbee48ac89f5"
EN_QUEST_ENTRIES = range(4791, 5342)
JSON_TYPES = {dict: "object", list: "array", str: "string", int: "integer",
              float: "number", bool: "boolean", type(None): "null"}


def unique_keys(pairs):
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError(f"Duplicate JSON key {key!r}")
        record[key] = value
    return record


def schema(value, counts, path=""):
    counts[path][JSON_TYPES[type(value)]] += 1
    if isinstance(value, list):
        for child in value:
            schema(child, counts, f"{path}/*")
    elif isinstance(value, dict):
        for key, child in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            schema(child, counts, f"{path}/{escaped}")


def load_database(root):
    datasets = {}
    inventory = {}
    for file in sorted(root.rglob("*.json")):
        relative = file.relative_to(root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        path = relative.as_posix()
        raw = file.read_bytes()
        rows = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_keys)
        counts = defaultdict(Counter)
        schema(rows, counts)
        records = rows if isinstance(rows, list) else [rows]
        inventory[path] = {
            "sha256": sha256(raw).hexdigest(),
            "root_type": JSON_TYPES[type(rows)],
            "records": len(rows),
            "root_record_shapes": [
                {"keys_in_order": list(keys), "records": count}
                for keys, count in Counter(tuple(row) for row in records if isinstance(row, dict)).items()
            ],
            "schema": dict(sorted(counts.items())),
        }
        datasets[path] = rows
    if len(datasets) != 61:
        raise ValueError(f"Expected 61 database JSON files, found {len(datasets)}")
    return datasets, inventory


def read_item_texts(source, entries):
    entry_id, names = find_english_item_names(source, entries)
    pack = read_entry_data(source, entries[entry_id])
    start, end = u32(pack, 16), u32(pack, 20)
    if not 0 < start < end <= len(pack):
        raise ValueError("Invalid item description group boundaries")
    group = pack[start:end]
    table_size = 4 * (len(names) + 1)
    offsets = [u32(group, index * 4) for index in range(len(names) + 1)]
    if offsets[0] != table_size or offsets[-1] != 0xFFFFFFFF:
        raise ValueError("Invalid item description pointer table")
    offsets[-1] = len(group)
    descriptions = []
    for left, right in zip(offsets, offsets[1:]):
        if not table_size <= left < right <= len(group) or group[right - 1] != 0:
            raise ValueError(f"Invalid description span for item ID {len(descriptions)}")
        descriptions.append(group[left:group.index(0, left, right)].decode("utf-8"))
    return entry_id, [
        {"id": item_id, "name": name, "description": descriptions[item_id]}
        for item_id, name in enumerate(names)
    ]


def read_quests(source, entries):
    quests = []
    for entry_id in EN_QUEST_ENTRIES:
        payload, checksum = decode_quest(source, entries[entry_id])
        if checksum != "NA/EU":
            raise ValueError(f"Unexpected quest checksum region {checksum} at entry {entry_id}")
        visual = u32(payload, 0)
        english = u32(payload, u32(payload, visual + 0x14))
        text = []
        for index in range(6):
            address = u32(payload, english + 4 * index)
            if not 0 < address < len(payload):
                raise ValueError(f"Invalid quest text pointer at entry {entry_id}")
            text.append(payload[address:payload.index(0, address)].decode("utf-8"))
        ticks = u32(payload, visual + 16)
        quests.append({
            "archive_entry": entry_id, "quest_id": u16(payload, visual + 0x18),
            "checksum": checksum, "rank_code": payload[0x44], "map_id": payload[visual + 0x1C],
            "time_limit_ticks": ticks, "star_code": payload[visual + 0x1A],
            "fields": {
                "name": text[0], "goal-condition": text[1], "fail-condition": text[2],
                "quest-details": text[3], "client": text[5],
                "contract-fee": u32(payload, visual + 4), "reward": u32(payload, visual + 8),
                "time-limit": ticks // 1800 if ticks % 1800 == 0 else ticks / 1800,
            },
            "monster_display_text": text[4],
        })
    return quests


def normalize(value):
    return " ".join(value.split()) if isinstance(value, str) else value


def grouped(records, key):
    groups = defaultdict(list)
    for index, record in enumerate(records):
        groups[key(record)].append(index)
    return groups


def compare_items(rows, game):
    by_name = grouped(game[1:], lambda item: item["name"])
    public = grouped(rows, lambda item: item["name"])
    records, proposed, used_ids = [], [], set()
    for index, row in enumerate(rows):
        candidates = [game[game_index + 1] for game_index in by_name.get(row["name"], [])]
        exact = len(candidates) == 1 and len(public[row["name"]]) == 1
        comparison = {"row": index, "name": row["name"], "candidates": candidates}
        candidate = dict(row)
        if exact and normalize(row["description"]) == normalize(candidates[0]["description"]):
            item_id = candidates[0]["id"]
            if item_id in used_ids or ("id" in row and row["id"] != item_id):
                raise ValueError(f"Conflicting proposed item ID {item_id}")
            candidate["id"] = item_id
            used_ids.add(item_id)
            comparison.update(status="verified", id=item_id)
        elif exact:
            comparison.update(status="description-differs", published_description=row["description"])
        else:
            comparison["status"] = "ambiguous-name" if candidates else "unmatched-name"
        records.append(comparison)
        proposed.append(candidate)
    return {
        "counts": Counter(row["status"] for row in records),
        "records": records,
        "unmapped_game_items": [row for row in game[1:] if row["id"] not in used_ids],
    }, proposed


def check_item_proposal(original, proposed):
    if len(original) != len(proposed):
        raise ValueError("Item row count changed")
    ids = []
    for before, after in zip(original, proposed):
        retained = {key: value for key, value in after.items() if key in before}
        if list(retained) != list(before) or json.dumps(retained) != json.dumps(before):
            raise ValueError("An existing value, property, type, or order changed")
        if set(after) - set(before) - {"id"}:
            raise ValueError("Unexpected property addition")
        if "id" in after:
            ids.append(after["id"])
    if any(type(item_id) is not int for item_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("Invalid or duplicate item IDs")


def quest_key(fields):
    return normalize(fields["name"]), normalize(fields.get("goal-condition"))


def quest_candidates(row, candidates, game):
    if len(candidates) <= 1:
        return candidates
    for field in ("quest-details", "client"):
        value = normalize(row.get(field))
        if value:
            matches = [index for index in candidates if normalize(game[index]["fields"][field]) == value]
            if matches:
                candidates = matches
    return candidates


def compare_quests(datasets, game):
    indexed = [(path, index, row) for path, rows in datasets.items() if path.startswith("Quests/")
               for index, row in enumerate(rows)]
    game_keys = grouped(game, lambda record: quest_key(record["fields"]))
    game_titles = grouped(game, lambda record: normalize(record["fields"]["name"]))
    links = [
        quest_candidates(row, game_keys.get(quest_key(row), []), game)
        for _, _, row in indexed
    ]
    claim_counts = Counter(candidate for candidates in links for candidate in candidates)
    reports = defaultdict(list)
    used = set()
    for (path, index, row), candidates in zip(indexed, links):
        key = quest_key(row)
        eligible = key[1] and len(candidates) == 1 and claim_counts[candidates[0]] == 1
        if eligible:
            game_index = candidates[0]
            quest = game[game_index]
            fields = quest["fields"]
            differences = {
                field: {"published": row[field], "english": value}
                for field, value in fields.items()
                if field in row and normalize(row[field]) != normalize(value)
            }
            matches = [field for field in fields if field in row and field not in differences]
            used.add(game_index)
            reports[path].append({
                "row": index, "name": row["name"], "quest_id": quest["quest_id"],
                "archive_entry": quest["archive_entry"], "status": "fields-differ" if differences else "fields-agree",
                "identity_evidence": ["name", "goal-condition"] + [
                    field for field in ("quest-details", "client")
                    if len(game_keys[key]) > 1 and field in matches
                ],
                "matching_fields": matches, "differences": differences,
                "unverified_fields": [field for field in row if field not in fields],
            })
        else:
            related = candidates or game_titles.get(key[0], [])
            reports[path].append({
                "row": index, "name": row["name"], "published_goal": row.get("goal-condition"),
                "status": "ambiguous" if candidates else "unmatched-key",
                "candidates": [game[game_index] for game_index in related],
            })
    return {
        "files": {
            path: {"counts": Counter(row["status"] for row in records), "records": records}
            for path, records in reports.items()
        },
        "unlinked_game_quests": [quest for index, quest in enumerate(game) if index not in used],
    }


def reference_rows(datasets):
    """Yield name references from fields whose roles are identifiable from the schema."""
    for path, rows in datasets.items():
        for index, row in enumerate(rows):
            base = f"/{index}"
            if path in {"item-notes.json", "items-combine.json"}:
                for field in ("name", "materialA", "materialB"):
                    if field in row:
                        yield path, f"{base}/{field}", "items.json", row[field]
            if path == "maps.json":
                for area_index, area in enumerate(row["areas"]):
                    for position_index, position in enumerate(area["positions"]):
                        for material_index, name in enumerate(position["materials"]):
                            yield path, f"{base}/areas/{area_index}/positions/{position_index}/materials/{material_index}", "items.json", name
            if path in {"Weapons/weapons-craft.json", "armors.json", "decorations.json"}:
                for material_index, material in enumerate(row.get("materials", [])):
                    yield path, f"{base}/materials/{material_index}/name", "items.json", material["name"]
            if path == "Weapons/weapons-craft.json":
                for field in ("name", "upgrade-from"):
                    if row[field]:
                        yield path, f"{base}/{field}", "Weapons/weapons.json", row[field]
            if path.startswith("Monsters/") and "monster" in row:
                yield path, f"{base}/monster", "Monsters/monsters.json", row["monster"]
            if path == "Monsters/monsters-material.json":
                for type_index, reward in enumerate(row["types"]):
                    for material_index, material in enumerate(reward["materials"]):
                        yield path, f"{base}/types/{type_index}/materials/{material_index}/name", "items.json", material["name"]
            if path.startswith("Quests/"):
                for monster_index, name in enumerate(row.get("main-monsters", [])):
                    yield path, f"{base}/main-monsters/{monster_index}", "Monsters/monsters.json", name


def compare_references(datasets, items):
    targets = ("items.json", "Weapons/weapons.json", "Monsters/monsters.json")
    catalogs = {target: Counter(row["name"] for row in datasets[target]) for target in targets}
    item_ids = defaultdict(list)
    for item in items[1:]:
        item_ids[item["name"]].append(item["id"])
    reports = defaultdict(lambda: {"catalog_counts": Counter(), "english_item_counts": Counter(), "review": []})
    for path, location, target, name in reference_rows(datasets):
        report = reports[path]
        count = catalogs[target][name]
        status = "unique" if count == 1 else "ambiguous" if count else "unmatched"
        report["catalog_counts"][status] += 1
        ids = item_ids.get(name, []) if target == "items.json" else None
        if ids is not None:
            report["english_item_counts"]["unique" if len(ids) == 1 else "ambiguous" if ids else "unmatched"] += 1
        if status != "unique" or (ids is not None and len(ids) != 1):
            report["review"].append({
                "pointer": location, "target": target, "name": name,
                "catalog_status": status, "english_item_id_candidates": ids,
            })
    return dict(reports)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_gathering(path, quests, items, entry_id):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["archive_base_disc_id"] != "ULUS10391" or data["source_entries"]["item_string_pack_entry"] != entry_id:
        raise ValueError("Gathering export uses a different region or item string pack")
    fields = ("quest_id", "map_id", "rank_code")
    fresh = {quest["archive_entry"]: tuple(quest[field] for field in fields) for quest in quests}
    previous = {quest["archive_entry"]: tuple(quest[field] for field in fields) for quest in data["quests"]}
    if fresh != previous or len(previous) != len(data["quests"]):
        raise ValueError("Gathering quest records differ from fresh binary reads")
    for key, labels in data["items"].items():
        if items[int(key)]["name"] != labels["name_en"]:
            raise ValueError(f"Gathering item name differs at item ID {key}")
    methods = Counter(spot["method"] for quest in data["quests"] for spot in quest["spots"])
    if methods != data["spot_counts"]:
        raise ValueError("Gathering spot counts disagree with the export manifest")
    return {
        "source": str(path.resolve()), "source_entries": data["source_entries"],
        "verified_quest_headers": len(fresh), "verified_item_names": len(data["items"]),
        "map_variants_used_by_quests": len({quest["map_id"] for quest in quests}),
        "spots_by_method": methods,
        "scope": "Fresh binary quest and item identity cross-check of the extraction export; public map joins pending.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path, help="New report directory outside the database checkout")
    parser.add_argument("--revision", help="Git revision of the database snapshot, if known")
    parser.add_argument("--gathering", type=Path, help="Cross-check an existing English gathering export")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(args.database.resolve()) or output.exists():
        parser.error("Output must be a new directory outside the database checkout")

    datasets, inventory = load_database(args.database)
    with args.archive.open("rb") as source:
        digest = file_digest(source, "sha256").hexdigest()
        if digest != EN_SHA256:
            parser.error("Archive differs from the audited ULUS10391 v1.01 build")
        source.seek(0)
        entries = read_index(source)
        entry_id, items = read_item_texts(source, entries)
        quests = read_quests(source, entries)

    item_report, proposal = compare_items(datasets["items.json"], items)
    check_item_proposal(datasets["items.json"], proposal)
    quest_report = compare_quests(datasets, quests)
    references = compare_references(datasets, items)
    gathering = check_gathering(args.gathering, quests, items, entry_id) if args.gathering else None
    output.mkdir(parents=True)
    (output / "proposals").mkdir()
    write_json(output / "repository-inventory.json", {"revision": args.revision, "files": inventory})
    write_json(output / "english-items.json", {"archive_entry": entry_id, "items": items})
    write_json(output / "english-quests.json", {"archive_sha256": digest, "quests": quests})
    write_json(output / "item-comparison.json", item_report)
    write_json(output / "quest-comparison.json", quest_report)
    write_json(output / "name-references.json", references)
    if gathering is not None:
        write_json(output / "gathering-crosscheck.json", gathering)
    write_json(output / "proposals" / "items.json", proposal)
    print(f"{len(inventory)} datasets, {len(entries)} archive entries, {len(quests)} verified quest checksums")
    print(f"Items: {dict(item_report['counts'])}")
    print(f"Reports: {output}")


if __name__ == "__main__":
    main()
