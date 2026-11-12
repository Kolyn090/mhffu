"""Generate a browsable table of contents for the North American English MHFU archive."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct

from decode_mhfu import (
    SECTOR_BYTES, QuestChecksumError, decode_quest, entry_chunks, read_entry_data, read_index,
)
from extract_gathering import find_english_item_names, parse_item_names, quest_title, u16, u32


EN_SHA256 = "d7e5b5cebe07fe00ae1167ed6779f8a6d246ffe35842878a1aeadbee48ac89f5"
ENTRY_COUNT = 6657
QUEST_COUNT = 551
HEADER_BYTES = 64
SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "PNG image"),
    (b".TMH0.14", "TMH texture"),
    (b"MIG.00.1PSP", "PSP GIM image"),
    (b"MWo3", "MWo3 overlay"),
    (b"~SCE", "PSP SCE module"),
    (b"~PSP", "PSP module"),
    (b"\x7fELF", "ELF executable"),
    (b"PSMF", "PSMF movie"),
    (b"dbsT", "dbsT sound table"),
    (b"pmo\0", "PMO model"),
)


def archive_digest(source):
    source.seek(0)
    return hashlib.file_digest(source, "sha256").hexdigest()


def entry_headers(source, entries, total_bytes):
    previous_end = entries[0].byte_offset
    headers = []
    for expected_id, entry in enumerate(entries):
        start = entry.byte_offset
        end = start + entry.sector_span_bytes
        if (entry.entry_id != expected_id or start != previous_end
                or not 0 <= start <= end <= total_bytes or start % SECTOR_BYTES or end % SECTOR_BYTES
                or not 0 <= entry.readable_bytes <= entry.sector_span_bytes):
            raise ValueError(f"Invalid indexed byte range for entry {expected_id}")
        headers.append(read_entry_data(source, entry, min(HEADER_BYTES, entry.readable_bytes)))
        previous_end = end
    if previous_end != total_bytes:
        raise ValueError("Last indexed byte range does not reach the end of the archive")
    return headers


def verify_quest(source, entry):
    try:
        payload, region = decode_quest(source, entry)
    except QuestChecksumError:
        raise
    except ValueError:
        return None
    if region != "NA/EU":
        raise ValueError(f"Unexpected quest checksum salt at entry {entry.entry_id}: {region}")
    visual = u32(payload, 0)
    return {
        "quest_id": u16(payload, visual + 0x18),
        "title": quest_title(payload, visual),
        "map_id": payload[visual + 0x1C],
        "checksum_region": region,
    }


def pac_member_count(source, entry, header):
    """Check the offset/size table used by the existing stage PAC reader."""
    if len(header) < 12:
        return None
    count = u32(header, 0)
    table_bytes = 4 + count * 8
    # A bounded probe keeps unrecognized integer prefixes cheap to test.
    if not 1 <= count <= 256 or table_bytes > entry.readable_bytes:
        return None
    table = header[:table_bytes]
    if len(table) < table_bytes:
        table = read_entry_data(source, entry, table_bytes)
    members = list(struct.iter_unpack("<II", table[4:]))
    if any(size for _, size in members) and all(
        (offset == 0 and size == 0) or table_bytes <= offset <= entry.readable_bytes - size
        for offset, size in members
    ):
        return count
    return None


def identify_type(source, entry, header, quest):
    if quest is not None:
        return "2NDG quest", "Inner 2NDG signature and verified salted SHA-1"
    for signature, file_type in SIGNATURES:
        if header.startswith(signature):
            return file_type, f"Magic at byte 0: {signature.hex()}"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "RIFF/WAVE audio", "RIFF at byte 0 and WAVE at byte 8"
    if header.startswith(b"Head") and header[32:36] == b"Prog":
        return "Head/Prog sound bank header", "Head at byte 0 and Prog at byte 32"
    if header.startswith(b"\x17\0\0\0\x08\0\0\0"):
        try:
            parse_item_names(read_entry_data(source, entry))
        except (ValueError, struct.error):
            pass
        else:
            return "Localized item string pack", "23-group directory and validated 1,261-slot item-name table"
    count = pac_member_count(source, entry, header)
    if count is not None:
        return "PAC-style container", f"{count} member offset/size pairs checked against the indexed range"
    return None, None


def build_entries(source, entries, headers):
    english_strings, _ = find_english_item_names(source, entries)
    records = []
    for entry, header in zip(entries, headers):
        quest = verify_quest(source, entry)
        file_type, type_evidence = identify_type(source, entry, header, quest)
        overlay_name = None
        if file_type == "MWo3 overlay" and len(header) == HEADER_BYTES:
            name, terminator, _ = header[32:64].partition(b"\0")
            if terminator and re.fullmatch(rb"[A-Za-z0-9_-]+\.ovl", name):
                overlay_name = name.decode("ascii")
        record = {
            "entry_id": entry.entry_id,
            "mapped_path": overlay_name,
            "mapping_status": "confirmed" if overlay_name else None,
            "mapping_evidence": {"source": "NUL-terminated name at MWo3 offset 0x20", "scope": "embedded basename"}
            if overlay_name else None,
            "first_sector": entry.byte_offset // SECTOR_BYTES,
            "start_byte": entry.byte_offset,
            "end_byte_exclusive": entry.byte_offset + entry.sector_span_bytes,
            "allocated_bytes": entry.sector_span_bytes,
            "indexed_payload_bytes": entry.indexed_payload_bytes,
            "header_hex": header.hex(),
            "region": {
                "archive_base_disc_id": "ULUS10391",
                "verified_quest_checksum_region": quest["checksum_region"] if quest else None,
                "verified_item_name_table_language": "en" if entry.entry_id == english_strings else None,
            },
            "outer_encrypted": entry.outer_encrypted,
            "file_type": file_type,
            "file_type_evidence": type_evidence,
            "overlay_name": overlay_name,
            "quest": quest,
        }
        records.append(record)
    return records


def content_key(entry, header):
    # Matching prefixes only select candidates. Full-region hashes decide the match.
    return entry.readable_bytes, entry.indexed_payload_bytes, header


def content_digest(source, entry):
    digest = hashlib.sha256()
    for chunk in entry_chunks(source, entry, entry.readable_bytes):
        digest.update(chunk)
    return digest.hexdigest()


def reference_counts(toc):
    entries = toc["entries"]
    regions = Counter(row["region"]["verified_quest_checksum_region"] for row in entries
                      if row["region"]["verified_quest_checksum_region"])
    return {
        "total_bytes": toc["archive"]["bytes"],
        "sector_size": toc["archive"]["sector_bytes"],
        "index_decoding_method": "Plaintext sector index",
        "index_end_byte_exclusive": toc["archive"]["index_end_byte_exclusive"],
        "entry_count": len(entries),
        "entries_with_indexed_payload_bytes": sum(row["indexed_payload_bytes"] is not None for row in entries),
        "entries_with_mapped_paths": sum(row["mapped_path"] is not None for row in entries),
        "verified_quests": sum(regions.values()),
        "quest_checksum_regions": dict(regions),
    }


def validate_reference(toc, entries, headers):
    if len(toc["entries"]) != len(entries):
        raise ValueError("Japanese TOC and archive have different entry counts")
    for row, entry, header in zip(toc["entries"], entries, headers):
        if (row["entry_id"] != entry.entry_id or row["start_byte"] != entry.byte_offset
                or row["allocated_bytes"] != entry.sector_span_bytes
                or row["indexed_payload_bytes"] != entry.indexed_payload_bytes
                or not header.hex().startswith(row["header_hex"].lower())):
            raise ValueError(f"Japanese TOC disagrees with archive entry {entry.entry_id}")


def infer_paths(source, entries, headers, records, jp_source, jp_entries, jp_headers, toc):
    en_groups = defaultdict(list)
    for entry, header, row in zip(entries, headers, records):
        if len(header) == HEADER_BYTES and row["mapped_path"] is None and row["quest"] is None:
            en_groups[content_key(entry, header)].append(entry)

    jp_groups = defaultdict(list)
    for entry, header in zip(jp_entries, jp_headers):
        key = content_key(entry, header)
        if key in en_groups:
            jp_groups[key].append(entry)

    for key, japanese in jp_groups.items():
        japanese_digests = defaultdict(list)
        for entry in japanese:
            japanese_digests[content_digest(jp_source, entry)].append(entry)
        english_digests = defaultdict(list)
        for entry in en_groups[key]:
            english_digests[content_digest(source, entry)].append(entry)
        for digest, english in english_digests.items():
            matches = japanese_digests.get(digest, [])
            if len(matches) != 1 or len(english) != 1:
                continue
            en_entry, jp_entry = english[0], matches[0]
            path = toc["entries"][jp_entry.entry_id]["mapped_path"]
            if not path:
                continue
            row = records[en_entry.entry_id]
            row["mapped_path"] = path
            row["mapping_status"] = "inferred"
            row["mapping_evidence"] = {
                "source": "Unique full-region SHA-256 match to a Japanese TOC entry",
                "jp_entry_id": jp_entry.entry_id,
                "compared_bytes": en_entry.readable_bytes,
                "compared_region": "indexed payload" if en_entry.indexed_payload_bytes is not None else "allocated span",
                "sha256": digest,
            }


def compare_japanese(source, entries, headers, records, toc_path, archive_path):
    with toc_path.open(encoding="utf-8-sig") as file:
        toc = json.load(file)
    comparison = {
        "reference_release": toc["archive"]["release"],
        "reference_archive_sha256": toc["archive"]["sha256"],
        "reference_path_map_source": toc["path_map_source"],
        "japanese_toc_statistics": reference_counts(toc),
        "japanese_archive_verified": False,
    }
    if archive_path is None:
        return comparison
    with archive_path.open("rb") as jp_source:
        if archive_digest(jp_source) != toc["archive"]["sha256"]:
            raise ValueError("Japanese archive hash does not match the Japanese TOC")
        jp_entries = read_index(jp_source)
        jp_headers = entry_headers(jp_source, jp_entries, toc["archive"]["bytes"])
        validate_reference(toc, jp_entries, jp_headers)
        infer_paths(source, entries, headers, records, jp_source, jp_entries, jp_headers, toc)
        jp_overlays = {
            header[32:64].split(b"\0", 1)[0].decode("ascii"): entry.entry_id
            for entry, header in zip(jp_entries, jp_headers) if header.startswith(b"MWo3")
        }
    shared_overlays = {}
    for row in records:
        name = row["overlay_name"]
        if name in jp_overlays:
            jp_id = jp_overlays[name]
            shared_overlays[name] = (jp_id, row["entry_id"])
            jp_path = toc["entries"][jp_id]["mapped_path"]
            if jp_path and PurePosixPath(jp_path).name == name:
                row["mapping_evidence"]["jp_reference_path"] = jp_path
                row["mapping_evidence"]["jp_entry_id"] = jp_id
    comparison.update({
        "japanese_archive_verified": True,
        "shared_embedded_overlay_names": len(shared_overlays),
        "shared_overlay_names_at_different_entry_ids": sum(jp != en for jp, en in shared_overlays.values()),
        "overlay_entry_id_examples": {
            name: {"jp": shared_overlays[name][0], "en": shared_overlays[name][1]}
            for name in ("game_sub.ovl", "stage000.ovl", "stage266.ovl") if name in shared_overlays
        },
    })
    return comparison


def summarize(records):
    statuses = Counter(row["mapping_status"] or "unmapped" for row in records)
    types = Counter(row["file_type"] for row in records if row["file_type"] is not None)
    quest_regions = Counter(row["quest"]["checksum_region"] for row in records if row["quest"] is not None)
    return {
        "entries": len(records),
        "entries_with_mapped_paths": statuses["confirmed"] + statuses["inferred"],
        "path_mapping_counts": dict(sorted(statuses.items())),
        "entries_with_indexed_payload_bytes": sum(row["indexed_payload_bytes"] is not None for row in records),
        "entries_without_indexed_payload_bytes": sum(row["indexed_payload_bytes"] is None for row in records),
        "entries_with_identified_file_type": sum(types.values()),
        "entries_with_unknown_file_type": len(records) - sum(types.values()),
        "identified_file_types": dict(sorted(types.items())),
        "verified_quests": sum(quest_regions.values()),
        "quest_checksum_region_counts": dict(quest_regions),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="English DATA.BIN (ULUS10391 v1.01)")
    parser.add_argument("output", type=Path, help="New JSON file")
    parser.add_argument("--jp-toc", type=Path, help="Include statistics from the existing Japanese JSON")
    parser.add_argument("--jp-archive", type=Path, help="Verify Japanese path candidates by content; requires --jp-toc")
    args = parser.parse_args()
    if args.jp_archive is not None and args.jp_toc is None:
        parser.error("--jp-archive requires --jp-toc")
    if args.output.suffix.lower() != ".json" or args.output.exists():
        parser.error("Output must be a new .json file")

    with args.archive.open("rb") as source:
        archive_bytes = source.seek(0, 2)
        sha256 = archive_digest(source)
        if sha256 != EN_SHA256:
            raise ValueError("Archive SHA-256 differs from the verified ULUS10391 v1.01 DATA.BIN")
        entries = read_index(source)
        if len(entries) != ENTRY_COUNT or not entries[0].outer_encrypted:
            raise ValueError(f"Expected the encrypted {ENTRY_COUNT}-entry index")
        headers = entry_headers(source, entries, archive_bytes)
        records = build_entries(source, entries, headers)
        comparison = None
        if args.jp_toc is not None:
            comparison = compare_japanese(source, entries, headers, records, args.jp_toc, args.jp_archive)
    summary = summarize(records)
    if summary["verified_quests"] != QUEST_COUNT:
        raise ValueError(f"Expected {QUEST_COUNT} verified quest entries, found {summary['verified_quests']}")
    if comparison is not None:
        jp = comparison["japanese_toc_statistics"]
        comparison["english_minus_japanese"] = {
            "total_bytes": archive_bytes - jp["total_bytes"],
            "entry_count": len(records) - jp["entry_count"],
            "sector_size": SECTOR_BYTES - jp["sector_size"],
            "index_end_byte_exclusive": entries[0].byte_offset - jp["index_end_byte_exclusive"],
            "entries_with_indexed_payload_bytes": summary["entries_with_indexed_payload_bytes"]
            - jp["entries_with_indexed_payload_bytes"],
            "verified_quests": summary["verified_quests"] - jp["verified_quests"],
        }
        comparison["mapping_note"] = "Japanese TOC uses an external map. English coverage uses embedded names and optional verified content matches."

    toc = {
        "archive": {
            "filename": args.archive.name,
            "total_bytes": archive_bytes,
            "sha256": sha256,
            "detected_release": "Monster Hunter Freedom Unite, North America, ULUS10391 v1.01",
            "release_evidence": "Exact SHA-256 match to DATA.BIN previously verified against the local North American disc image",
            "sector_size": SECTOR_BYTES,
            "index_decoding_method": "PSP DATA.BIN outer cipher, seeded with sector zero via decode_mhfu.read_index",
            "index_start_byte": 0,
            "index_end_byte_exclusive": entries[0].byte_offset,
            "eof_marker_sector": archive_bytes // SECTOR_BYTES,
        },
        "field_notes": {
            "mapped_path": "Confirmed mappings contain an embedded archive-local basename. Inferred mappings inherit a Japanese reference path after a unique verified full-region hash match. Null means no supported path.",
            "allocated_bytes": "Sector allocation, possibly including padding. The exclusive end byte uses this allocation.",
            "indexed_payload_bytes": "Exact length supplied by the supplemental index. Null means the index supplies no exact length.",
            "header_hex": "First up to 64 readable bytes in hex after outer decryption, or as stored for clear entries. Quest headers retain their inner cipher.",
            "file_type": "Observed signature or validated structure. Null means unidentified by the checks in this exporter.",
            "region": "Container release, quest checksum salt when verified, and English item-name table identification where applicable. The NA/EU salt is shared by international quests.",
        },
        "summary": summary,
        "japanese_comparison": comparison,
        "entries": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(toc, file, indent=2, ensure_ascii=False)
        file.write("\n")
    print(f"Wrote {summary['entries']} entries, {summary['entries_with_mapped_paths']} mapped paths "
          f"and {summary['verified_quests']} verified quests to {args.output}")


if __name__ == "__main__":
    main()
