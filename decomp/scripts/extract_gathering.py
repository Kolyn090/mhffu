"""Export FUComplete and English MHFU quest gathering and fish-spawn tables."""

import argparse
import json
import math
import re
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from decode_mhfu import QuestChecksumError, decode_quest, read_entry_data, read_index


MAP_NAMES = (
    "Pokke Village", "Fortress (Day)", "Forest and Hills (Day)", "Desert (Day)",
    "Swamp (Day)", "Volcano (Day)", "Jungle (Day)", "Castle Schrade",
    "Battleground", "Great Arena", "Arena", "Snowy Mountains (Day)", "Town",
    "Tower (Kirin)", "Tower (Yama Tsukami)", "Tower (Fatalis)",
    "Forest and Hills (Night)", "Desert (Night)", "Swamp (Night)",
    "Volcano (Night)", "Jungle (Night)", "Snowy Mountains (Night)", "Moat Arena",
    "Snowy Mountains Peak", None, None, "Old Jungle", "Old Desert",
    "Old Swamp", "Old Volcano", "Great Forest (Day)", "Great Forest (Night)",
)
RANK_NAMES = ("Easy", "Low", "High", "Treasure", "Training", "G")
NODE_TYPES = {0: "gather", 3: "mine", 4: "bug_net"}
NODE = struct.Struct("<4f4H")
NODE_END = 0xBF800000  # The game ends an area list when the next x coordinate is -1.0.

# Addresses in the supported ULJM05500 game_sub.ovl build.
MAP_STAGE_TABLE = 0x09CDF678
FISH_DEFINITIONS = 0x09CCE3B0
TUTORIAL_FISH = 0x09CE03A8
FISH_KIND_COUNT = 37
TUTORIAL_MISSION_FLAG = 1 << 23
STAGE_COUNT = 267


@dataclass(frozen=True)
class GatheringLayout:
    disc_id: str
    game_sub_base: int
    map_table: int
    fish_definitions: int
    tutorial_fish: int
    language: str
    stage_pac_base: int


JP_LAYOUT = GatheringLayout("ULJM05500", 0x09C14280, MAP_STAGE_TABLE, FISH_DEFINITIONS, TUTORIAL_FISH, "ja", 5756)
# ULUS10391 v1.01. Table contents and pointers were checked in this build's own game_sub.
EN_LAYOUT = GatheringLayout("ULUS10391", 0x09C19100, 0x09CE4808, 0x09CD3538, 0x09CE5538, "en", 5808)


def u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def read_entry(source, entry):
    return read_entry_data(source, entry)


def read_item_names(source, entry):
    """Read group 1 of str_tbl.pac, the UTF-8 item-name offset table."""
    return parse_item_names(read_entry(source, entry))


def parse_item_names(data):
    if u32(data, 0) < 3 or u32(data, 4) != 8:
        raise ValueError("Unexpected item string pack header")
    start, end = u32(data, 12), u32(data, 16)
    if not 0 < start < end <= len(data):
        raise ValueError("Invalid item-name group boundaries")
    group = data[start:end]
    if u32(group, 0) != 4 * 1262:
        raise ValueError("Unsupported item-name table")
    names = []
    for item_id in range(1261):
        offset = u32(group, item_id * 4)
        if not 4 * 1262 <= offset < len(group):
            raise ValueError(f"Invalid item-name offset for item {item_id}")
        names.append(group[offset:group.index(0, offset)].decode("utf-8"))
    return names


def read_maps(game_sub, base, map_table=MAP_STAGE_TABLE):
    """Resolve map slots to stage IDs using the same table as the game."""
    maps = {}
    for map_id, name in enumerate(MAP_NAMES):
        count, address = struct.unpack_from("<II", game_sub, map_table - base + map_id * 8)
        if not count and name is None:
            continue
        offset = address - base
        if name is None or not 1 <= count <= 16 or not 0 <= offset <= len(game_sub) - 2 * count:
            raise ValueError(f"Unsupported stage list for map {map_id}")
        stages = struct.unpack_from(f"<{count}H", game_sub, offset)
        if any(stage >= STAGE_COUNT for stage in stages):
            raise ValueError(f"Out-of-range stage ID for map {map_id}")
        maps[map_id] = {"name": name, "stage_ids_by_area_index": stages}
    return maps


def find_stage_overlays(source, entries):
    """Find the game_sub and stage overlays by their embedded MWo3 names."""
    overlays = {}
    for entry in entries:
        if entry.readable_bytes < 64:
            continue
        header = read_entry_data(source, entry, 64)
        if header.startswith(b"MWo3"):
            name = header[32:64].split(b"\0", 1)[0]
            if name == b"game_sub.ovl" or re.fullmatch(rb"stage[0-9]{3}\.ovl", name):
                if name in overlays:
                    raise ValueError(f"Duplicate overlay name {name!r}")
                overlays[name] = entry
    stage_names = [f"stage{stage:03}.ovl".encode("ascii") for stage in range(STAGE_COUNT)]
    missing = [name for name in [b"game_sub.ovl", *stage_names] if name not in overlays]
    if missing:
        raise ValueError(f"Missing {len(missing)} required overlays, starting with {missing[0]!r}")
    return overlays[b"game_sub.ovl"], [overlays[name] for name in stage_names]


def find_english_item_names(source, entries):
    english_names = []
    for entry in entries:
        if entry.readable_bytes >= 8 and read_entry_data(source, entry, 8) == b"\x17\0\0\0\x08\0\0\0":
            try:
                names = read_item_names(source, entry)
            except (ValueError, struct.error):
                continue
            if (names[1], names[7], names[161], names[246]) == (
                "Book of Combos 1", "Potion", "Honey", "Insect Husk"
            ):
                english_names.append((entry.entry_id, names))
    if len(english_names) != 1:
        raise ValueError(f"Expected one English item string pack, found {len(english_names)}")
    return english_names[0]


def stage_resources(source, entries):
    """Resolve and verify region-specific stage resources for the extractors."""
    if entries and entries[0].outer_encrypted:
        layout = EN_LAYOUT
        game_entry, stage_entries = find_stage_overlays(source, entries)
    else:
        layout = JP_LAYOUT
        if len(entries) <= 5490 + STAGE_COUNT - 1:
            raise ValueError("Archive is missing the expected stage overlays")
        game_entry = entries[56]
        stage_entries = entries[5490:5490 + STAGE_COUNT]
    game_sub = read_entry(source, game_entry)
    base = u32(game_sub, 8)
    if (game_sub[:4] != b"MWo3" or game_sub[32:64].split(b"\0")[0] != b"game_sub.ovl"
            or base != layout.game_sub_base):
        raise ValueError(f"Unsupported game_sub build at entry {game_entry.entry_id}")
    return layout, game_entry, game_sub, stage_entries


def gathering_resources(source, entries):
    """Load region-specific resources, then use the same data readers for both builds."""
    layout, game_entry, game_sub, stage_entries = stage_resources(source, entries)
    if layout.language == "en":
        name_entry_id, item_names = find_english_item_names(source, entries)
    else:
        name_entry_id = 15
        item_names = read_item_names(source, entries[name_entry_id])
    base = layout.game_sub_base
    maps = read_maps(game_sub, base, layout.map_table)
    fish_items = [u16(game_sub, layout.fish_definitions - base + 12 * fish)
                  for fish in range(FISH_KIND_COUNT)]
    if fish_items[0] != 0 or any(not 0 < item < len(item_names) for item in fish_items[1:]):
        raise ValueError("Invalid fish item definitions")
    tutorial_fish = read_weights(game_sub, layout.tutorial_fish - base, len(game_sub), fishing=True)
    fish_stages = {}
    for stage_id, stage_entry in enumerate(stage_entries):
        result = fishing_spots(read_entry(source, stage_entry), stage_id)
        if result is not None:
            fish_stages[stage_id] = result
    resources = {
        "game_sub_entry": game_entry.entry_id,
        "item_string_pack_entry": name_entry_id,
        "stage_overlay_entries": [entry.entry_id for entry in stage_entries],
    }
    return layout, item_names, maps, fish_stages, fish_items, tutorial_fish, resources


def fishing_spots(stage, stage_id):
    """Resolve the stage's rank-table, spot-count and coordinate getters."""
    base, text_size = struct.unpack_from("<II", stage, 8)
    expected_name = f"stage{stage_id:03}.ovl".encode("ascii")
    if stage[:4] != b"MWo3" or stage[32:64].split(b"\0")[0] != expected_name:
        raise ValueError(f"Unsupported overlay for stage {stage_id}")
    for offset in range(64, 64 + text_size - 51, 4):
        words = struct.unpack_from("<13I", stage, offset)
        # MIPS getter: index by rank, load the table address, return its pointer.
        if (words[0], words[1], words[4], words[5], words[6]) != (
            0x30A200FF, 0x00021880, 0x00431021, 0x03E00008, 0x8C420000
        ):
            continue
        if (words[2] >> 16, words[3] >> 16, words[8], words[9] >> 16,
                words[10] >> 16, words[11], words[12] >> 16) != (
            0x3C02, 0x2442, 0x03E00008, 0x2402, 0x3C02, 0x03E00008, 0x2442
        ):
            raise ValueError(f"Unrecognized fishing getters in stage {stage_id}")

        def data_offset(lui, addiu):
            signed_low, = struct.unpack("<h", struct.pack("<H", addiu & 0xFFFF))
            return ((lui & 0xFFFF) << 16) + signed_low - base

        rank_table = data_offset(words[2], words[3])
        count = words[9] & 0xFFFF
        positions = data_offset(words[10], words[12])
        if not (64 + text_size <= rank_table <= len(stage) - 4 * len(RANK_NAMES)
                and 0 < count <= 16 and 64 + text_size <= positions <= len(stage) - 32 * count):
            raise ValueError(f"Invalid fishing data addresses in stage {stage_id}")
        tables = [
            read_weights(stage, address - base, len(stage), fishing=True)
            for address in struct.unpack_from(f"<{len(RANK_NAMES)}I", stage, rank_table)
        ]
        points = [struct.unpack_from("<3f", stage, positions + 32 * spot) for spot in range(count)]
        return points, tables
    return None


def read_weights(data, offset, end, *, fishing=False):
    """Read (weight, ID) pairs through the format's sentinel."""
    record = struct.Struct("<BB" if fishing else "<HH")
    sentinel = 0xFF if fishing else 0xFFFF
    if not 0 <= offset <= end - record.size:
        raise ValueError("Invalid probability table pointer")
    weights = Counter()
    while offset + record.size <= end:
        weight, identifier = record.unpack_from(data, offset)
        if weight == sentinel:
            if weights.total() != 100:
                raise ValueError(f"Expected a total weight of 100, found {weights.total()}")
            return weights
        weights[identifier] += weight
        offset += record.size
    raise ValueError("Probability table has no terminator")


def gathering_spots(quest, stages):
    """Follow the area lists at header offset 0x1C and loot pointers at 0x24."""
    area_table = u32(quest, 0x1C)
    loot_table = u32(quest, 0x24)
    if not (0x80 <= loot_table <= area_table <= len(quest) - 4 * len(stages)):
        raise ValueError("Invalid gathering sections in quest")
    pointers = struct.unpack_from(f"<{len(stages)}I", quest, area_table)
    # The loot pointer array ends at the first nonempty area node list.
    loot_table_end = min((pointer for pointer in pointers if pointer), default=area_table)
    for area_index, start in enumerate(pointers):
        if not start:
            continue
        if not loot_table < start <= area_table - 4:
            raise ValueError(f"Invalid node pointer for area {area_index}")
        offset = start
        spot_index = 0
        while offset + 4 <= area_table:
            if u32(quest, offset) == NODE_END:
                break
            if offset + NODE.size > area_table:
                raise ValueError(f"Truncated node in area {area_index}")
            x, y, z, radius, selector, uses, kind, extra = NODE.unpack_from(quest, offset)
            if kind not in NODE_TYPES or not all(map(math.isfinite, (x, y, z, radius))):
                raise ValueError(f"Invalid node in area {area_index} at {offset:#x}")
            table_slot = loot_table + 4 * (selector & 0x7FFF)
            if table_slot + 4 > loot_table_end:
                raise ValueError(f"Invalid loot table index in area {area_index}")
            weights = read_weights(quest, u32(quest, table_slot), loot_table)
            yield {
                "area_index": area_index, "stage_id": stages[area_index],
                "spot_index": spot_index, "method": NODE_TYPES[kind],
                "xyz": [x, y, z], "interaction_radius": radius,
                "stored_uses": uses, "raw_node_parameter_0x16": extra,
                "quest_node_offset": offset,
                "outcomes": [
                    {"item_id": item or None, "nominal_percent": weight}
                    for item, weight in weights.items()
                ],
            }
            offset += NODE.size
            spot_index += 1
        else:
            raise ValueError(f"Missing node terminator for area {area_index}")


def quest_title(quest, visual_data):
    """Follow the first language table to its title (Japanese or English)."""
    language_index = u32(quest, visual_data + 0x14)
    title_offset = u32(quest, u32(quest, language_index))
    if not 0x80 <= title_offset < len(quest):
        raise ValueError("Invalid quest title pointer")
    return quest[title_offset:quest.index(0, title_offset)].decode("utf-8")


def quest_records(source, entries, maps, fish_stages, fish_items, tutorial_fish, *, english=False):
    """Discover all checksum-valid 2NDG quest entries in the archive."""
    for entry in entries:
        try:
            quest, region = decode_quest(source, entry)
        except QuestChecksumError:
            raise
        except ValueError:
            continue
        quest_id, map_id, rank_id = u16(quest, 0x64), quest[0x68], quest[0x44]
        try:
            stages = maps[map_id]["stage_ids_by_area_index"]
            rank = RANK_NAMES[rank_id]
            title = quest_title(quest, u32(quest, 0)) if english else None
            spots = list(gathering_spots(quest, stages))
            for area, stage in enumerate(stages):
                if stage not in fish_stages:
                    continue
                positions, tables = fish_stages[stage]
                weights = tutorial_fish if u32(quest, 0x4C) & TUTORIAL_MISSION_FLAG else tables[rank_id]
                for spot_index, xyz in enumerate(positions):
                    spots.append({
                        "area_index": area, "stage_id": stage,
                        "spot_index": spot_index, "method": "fish_spawn", "xyz": xyz,
                        "outcomes": [
                            {"fish_kind_id": fish, "item_id": fish_items[fish] or None,
                             "nominal_percent": weight}
                            for fish, weight in weights.items()
                        ],
                    })
        except (ValueError, IndexError, KeyError, struct.error) as error:
            raise ValueError(f"Cannot parse quest {quest_id} (entry {entry.entry_id}): {error}") from error
        record = {
            "archive_entry": entry.entry_id, "quest_id": quest_id,
            "map_id": map_id, "rank_code": rank_id, "rank": rank,
            "quest_checksum_region": region, "spots": spots,
        }
        if english:
            if region != "NA/EU":
                raise ValueError(f"Unexpected {region} checksum region for English quest {quest_id}")
            record["title_en"] = title
        yield record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--english-item-definitions", type=Path,
                        help="Optional item_manager.item_definitions.inc.cpp from mhp2g-decomp")
    args = parser.parse_args()
    try:
        with args.archive.open("rb") as source:
            entries = read_index(source)
            layout, item_names, maps, fish_stages, fish_items, tutorial_fish, resources = gathering_resources(source, entries)
            english = layout.language == "en"
            if english and args.english_item_definitions:
                raise ValueError("English item names come directly from this archive")
            quests = list(quest_records(source, entries, maps, fish_stages, fish_items, tutorial_fish,
                                        english=english))
        if not quests:
            raise ValueError("No checksum-valid 2NDG quests found")
        used_items = sorted({outcome["item_id"] for quest in quests for spot in quest["spots"]
                             for outcome in spot["outcomes"] if outcome["item_id"] is not None})
        items = {item: {f"name_{layout.language}": item_names[item]} for item in used_items}
        if args.english_item_definitions:
            text = args.english_item_definitions.read_text(encoding="utf-8")
            labels = re.findall(r"/\*\s*([^*]*?)\s*\*/\s*\{", text)
            if len(labels) != len(item_names):
                raise ValueError("Unexpected item count in English item definitions")
            for item in items:
                items[item]["name_en"] = labels[item]
        counts = Counter(spot["method"] for quest in quests for spot in quest["spots"])
        result = {
            "archive_base_disc_id": layout.disc_id,
            "notes": {
                "nominal_percent": "Stored weights per selection roll, out of 100. "
                                   "This excludes the random generator's modulo bias.",
                "fish_spawn": "Probability of the fish kind being spawned for a fish roll. "
                              "Catch rates depend on fishing behavior and bait.",
                "null_item_id": "The table selected no item or no fish.",
                "area_index": "Zero-based engine slot in the map's stage list.",
                "spot_index": "Zero-based within the area. Fish spots have their own sequence.",
                "scope": "Checksum-valid quests in this DATA.BIN. Does not include Pokke Farm "
                         "facilities or quests supplied separately from the archive.",
            },
            "maps": maps, "items": items, "spot_counts": counts, "quests": quests,
        }
        if english:
            result["source_entries"] = resources
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            output.write("\n")
        print(f"Exported {sum(counts.values()):,} spot records from {len(quests)} verified quests "
              f"across {len({quest['map_id'] for quest in quests})} map variants.")
    except (OSError, ValueError, IndexError, struct.error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
