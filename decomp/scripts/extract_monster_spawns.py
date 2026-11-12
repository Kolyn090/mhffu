"""Export large-monster tables and area spawn sets from FUComplete or English MHFU DATA.BIN."""

import argparse
import json
import math
import struct
import sys
from collections import Counter
from pathlib import Path

from decode_mhfu import QuestChecksumError, decode_quest, read_index
from extract_gathering import RANK_NAMES, quest_title, read_maps, stage_resources, u16, u32


# IDs follow EmType in the Portable 2nd G executable. Some are NPCs or objects.
MONSTER_NAMES = (
    "Dummy", "Rathian", "Fatalis", "Kelbi", "Mosswine", "Bullfango",
    "Yian Kut-Ku", "Lao-Shan Lung", "Cephadrome", "Felyne", "Veggie Elder",
    "Rathalos", "Aptonoth", "Genprey", "Diablos", "Khezu", "Velociprey",
    "Gravios", "Cat Cart", "Vespoid", "Gypceros", "Plesioth", "Basarios",
    "Melynx", "Hornetaur", "Apceros", "Monoblos", "Velocidrome", "Gendrome",
    "Rock", "Ioprey", "Iodrome", "Poogie", "Kirin", "Cephalos", "Giaprey",
    "Crimson Fatalis", "Pink Rathian", "Blue Yian Kut-Ku", "Purple Gypceros",
    "One-Eared Yian Garuga", "Silver Rathalos", "Gold Rathian", "Black Diablos",
    "White Monoblos", "Red Khezu", "Green Plesioth", "Black Gravios",
    "Daimyo Hermitaur", "Azure Rathalos", "Ashen Lao-Shan Lung", "Blangonga",
    "Congalala", "Rajang", "Kushala Daora", "Shen Gaoren", "Great Thunderbug",
    "Shakalaka", "Yama Tsukami", "Chameleos", "Rusted Kushala Daora", "Blango",
    "Conga", "Remobra", "Lunastra", "Teostra", "Hermitaur", "Shogun Ceanataur",
    "Bulldrome", "Anteka", "Popo", "White Fatalis", "Yama Tsukami", "Ceanataur",
    "Treshi", "Tigrex", "Akantor", "Giadrome", "Yian Garuga", "King Shakalaka",
    "Vespoid Queen", "Nargacuga", "Hypnocatrice", "Lavasioth", "Copper Blangonga",
    "Emerald Congalala", "Plum Daimyo Hermitaur", "Terra Shogun Ceanataur",
    "Ukanlos", "Furious Rajang",
)
SPAWN_RECORD_BYTES = 60
TABLE_HEADER = struct.Struct("<HHIII")
SCRIPT_PACKET = struct.Struct("<4h")


def spawn_records(quest, start, area_by_stage, *, area_stage=None):
    """Read 60-byte spawn records ending with a 16-bit 0xFFFF marker."""
    if start == 0:
        return []
    if not 0x80 <= start <= len(quest) - 2:
        raise ValueError(f"Invalid spawn pointer {start:#x}")
    records = []
    offset = start
    while offset + 2 <= len(quest):
        monster_id = u16(quest, offset)
        if monster_id == 0xFFFF:
            return records
        if offset + SPAWN_RECORD_BYTES > len(quest) or monster_id >= len(MONSTER_NAMES):
            raise ValueError(f"Invalid spawn record at {offset:#x}")
        variant, count, power, attr1, attr2 = struct.unpack_from("<H4B", quest, offset + 2)
        stage = u16(quest, offset + 8) if area_stage is None else area_stage
        xyz = struct.unpack_from("<3f", quest, offset + 0x20)
        if not all(map(math.isfinite, xyz)):
            raise ValueError(f"Invalid spawn coordinates at {offset:#x}")
        records.append({
            "monster_id": monster_id,
            "stage_id": stage,
            "area_index": area_by_stage.get(stage),
            "xyz": xyz,
            "yaw_raw": u32(quest, offset + 0x1C),
            "stored_count": count,
            "variant_code": variant,
            "power_code": power,
            "attribute_codes": [attr1, attr2],
            "record_offset": offset,
        })
        offset += SPAWN_RECORD_BYTES
    raise ValueError(f"Missing spawn list terminator at {start:#x}")


def table_headers(quest, start):
    """Read 16-byte headers. A zero first word ends the table."""
    if not 0x80 <= start <= len(quest) - 4:
        raise ValueError(f"Invalid spawn table pointer {start:#x}")
    offset = start
    while offset + 4 <= len(quest):
        if u32(quest, offset) == 0:
            return
        yield offset, TABLE_HEADER.unpack_from(quest, offset)
        offset += TABLE_HEADER.size
    raise ValueError(f"Missing spawn table terminator at {start:#x}")


def large_tables(quest, area_by_stage):
    # The pointer at 0x14 leads to the large-monster table headers directly.
    tables = []
    for offset, (selector, flags, _, _, records_ptr) in table_headers(quest, u32(quest, 0x14)):
        tables.append({
            "table_index": len(tables),
            "table_offset": offset,
            "header_selector": selector,
            "header_flags": flags,
            "spawns": spawn_records(quest, records_ptr, area_by_stage),
        })
    return tables


def small_tables(quest, area_by_stage):
    # The pointer at 0x18 leads to three setup pointers. Slots can share a table.
    index_offset = u32(quest, 0x18)
    if not 0x80 <= index_offset <= len(quest) - 16:
        raise ValueError("Invalid small-monster setup index")
    first, second, third, end = struct.unpack_from("<4I", quest, index_offset)
    if not all((first, second, third)) or end:
        raise ValueError("Expected three small-monster setup slots and a terminator")
    slots_by_pointer = {}
    for slot, pointer in enumerate((first, second, third)):
        slots_by_pointer.setdefault(pointer, []).append(slot)

    tables = []
    for pointer, slots in slots_by_pointer.items():
        areas = []
        for offset, (stage, flags, _, _, records_ptr) in table_headers(quest, pointer):
            areas.append({
                "stage_id": stage,
                "area_index": area_by_stage.get(stage),
                "table_offset": offset,
                "header_flags": flags,
                "spawns": spawn_records(quest, records_ptr, area_by_stage, area_stage=stage),
            })
        tables.append({"variant_slots": slots, "table_offset": pointer, "areas": areas})
    return tables


def quest_spawns(quest, entry_id, region, maps, language="ja"):
    visual_data = u32(quest, 0)
    quest_id = u16(quest, visual_data + 0x18)
    map_id = quest[visual_data + 0x1C]
    rank_id = quest[0x44]
    area_by_stage = {stage: area for area, stage in
                     enumerate(maps[map_id]["stage_ids_by_area_index"])}
    script_start, script_end = u32(quest, 0x10), u32(quest, 0x08)
    if not 0x80 <= script_start <= script_end <= len(quest):
        raise ValueError("Invalid quest script boundaries")
    return {
        "archive_entry": entry_id,
        "quest_id": quest_id,
        f"title_{language}": quest_title(quest, visual_data),
        "map_id": map_id,
        "rank_code": rank_id,
        "rank": RANK_NAMES[rank_id],
        "quest_checksum_region": region,
        "large_monster_tables": large_tables(quest, area_by_stage),
        "small_monster_setups": small_tables(quest, area_by_stage),
        "quest_script_packets": list(SCRIPT_PACKET.iter_unpack(quest[script_start:script_end])),
    }


def extract(archive):
    with archive.open("rb") as source:
        entries = read_index(source)
        layout, _, game_sub, _ = stage_resources(source, entries)
        maps = read_maps(game_sub, layout.game_sub_base, layout.map_table)
        quests = []
        for entry in entries:
            try:
                quest, region = decode_quest(source, entry)
            except QuestChecksumError:
                raise
            except ValueError:
                continue
            try:
                if layout.language == "en" and region != "NA/EU":
                    raise ValueError(f"Unexpected {region} checksum region for English quest")
                quests.append(quest_spawns(quest, entry.entry_id, region, maps, layout.language))
            except (ValueError, IndexError, KeyError, struct.error) as error:
                raise ValueError(f"Entry {entry.entry_id}: {error}") from error
    if not quests:
        raise ValueError("No checksum-valid 2NDG quests found")

    counts = Counter()
    used_monsters = set()
    quests_by_map = {map_id: [] for map_id in maps}
    for quest in quests:
        quests_by_map[quest["map_id"]].append(quest["quest_id"])
        for table in quest["large_monster_tables"]:
            counts["large"] += len(table["spawns"])
            used_monsters.update(spawn["monster_id"] for spawn in table["spawns"])
        for table in quest["small_monster_setups"]:
            for area in table["areas"]:
                counts["small"] += len(area["spawns"])
                used_monsters.update(spawn["monster_id"] for spawn in area["spawns"])
    for map_id, info in maps.items():
        info["quest_ids"] = quests_by_map[map_id]
    return {
        "archive_base_disc_id": layout.disc_id,
        "notes": {
            "area_index": "Zero-based slot in the quest map's stage list. Null means the raw stage "
                          "ID has no slot in that list.",
            "large_monster_tables": "Stored table order. Timing and activation depend on quest logic.",
            "small_monster_setups": "Setup slot 0 is initial. Other slots are alternative setups. "
                                    "Slots sharing one table are listed together.",
            "stored_count": "Raw count byte in the spawn record. It is not a count of simultaneously "
                            "active monsters.",
            "quest_script_packets": "Raw four-word script instructions in file order, stored as signed "
                                    "16-bit values. Runtime trigger conditions are not interpreted.",
            "scope": "Checksum-valid quests stored in this DATA.BIN. Positions are spawn record "
                     "coordinates. The export does not simulate patrols, respawn timing, or quests "
                     "stored outside the archive.",
        },
        "maps": maps,
        "monsters": {monster_id: MONSTER_NAMES[monster_id] for monster_id in sorted(used_monsters)},
        "spawn_record_counts": dict(counts),
        "quests": quests,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        result = extract(args.archive)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            output.write("\n")
    except (OSError, ValueError, IndexError, struct.error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    counts = result["spawn_record_counts"]
    quest_count = len(result["quests"])
    map_count = sum(bool(info["quest_ids"]) for info in result["maps"].values())
    print(f"Exported {counts.get('large', 0):,} large and {counts.get('small', 0):,} small-table "
          f"spawn records from {quest_count} verified quests across {map_count} map variants.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
