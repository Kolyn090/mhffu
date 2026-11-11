"""Inspect a FUComplete DATA.BIN with a readable index and decode 2NDG quests."""

import argparse
import csv
import hashlib
import json
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


SECTOR_BYTES = 2048
CHUNK_BYTES = 1024 * 1024
QUEST_MODULI = (0xFF9D, 0xFFA9, 0xFFC7, 0xFFF1)
QUEST_MULTIPLIERS = (0x1709, 0x3DF3, 0x747B, 0xB381)
QUEST_HASH_SALTS = {"JP": b"37wyS2Jfc3x5w9oG", "NA/EU": b"Vd6gh8F30wA86Ex5"}


@dataclass(frozen=True)
class ArchiveEntry:
    entry_id: int
    byte_offset: int
    sector_span_bytes: int
    indexed_payload_bytes: int | None

    @property
    def readable_bytes(self) -> int:
        if self.indexed_payload_bytes is not None:
            return self.indexed_payload_bytes
        return self.sector_span_bytes


def read_exact(source: BinaryIO, count: int) -> bytes:
    data = source.read(count)
    if len(data) != count:
        raise ValueError("Unexpected end of file")
    return data


def read_index(source: BinaryIO) -> list[ArchiveEntry]:
    """Read little-endian sector offsets followed by optional exact sizes."""
    archive_bytes = source.seek(0, os.SEEK_END)
    source.seek(0)
    first_sector, = struct.unpack("<I", read_exact(source, 4))
    index_bytes = first_sector * SECTOR_BYTES
    # The first sector offset doubles as the length of the index in sectors.
    # Check it before allocating a buffer for an unrecognized input.
    if archive_bytes % SECTOR_BYTES or not SECTOR_BYTES <= index_bytes < archive_bytes:
        raise ValueError("Expected a DATA.BIN with a readable sector index")
    source.seek(0)
    words = [value for (value,) in struct.iter_unpack("<I", read_exact(source, index_bytes))]
    end_sector = archive_bytes // SECTOR_BYTES
    offsets = [first_sector]
    for sector in words[1:]:
        if not offsets[-1] <= sector <= end_sector:
            raise ValueError("Invalid sector offset in DATA.BIN index")
        offsets.append(sector)
        if sector == end_sector:
            break
    else:
        raise ValueError("DATA.BIN index has no end-of-file sector")

    spans = [(end - start) * SECTOR_BYTES for start, end in zip(offsets, offsets[1:])]
    sizes = {}
    # After the EOF marker, (entry ID, byte length) pairs can trim sector padding.
    for cursor in range(len(offsets), len(words) - 1, 2):
        entry_id, size = words[cursor:cursor + 2]
        if not 0 < entry_id < len(spans) or size > spans[entry_id]:
            break
        sizes[entry_id] = size
    return [
        ArchiveEntry(entry_id, start * SECTOR_BYTES, spans[entry_id], sizes.get(entry_id))
        for entry_id, start in enumerate(offsets[:-1])
    ]


def extract_entry(source: BinaryIO, entry: ArchiveEntry, output: BinaryIO) -> None:
    """Copy one entry using at most a 1 MiB buffer."""
    source.seek(entry.byte_offset)
    remaining = entry.readable_bytes
    while remaining:
        data = read_exact(source, min(remaining, CHUNK_BYTES))
        output.write(data)
        remaining -= len(data)


def decode_quest(source: BinaryIO, entry: ArchiveEntry) -> tuple[bytes, str]:
    """Unwrap one encrypted quest and verify its payload before returning it."""
    if entry.readable_bytes < 32:
        raise ValueError("Quest entry is too small for its header")
    source.seek(entry.byte_offset)
    seeds = struct.unpack("<4H", read_exact(source, 8))
    keys = [seed or modulus for seed, modulus in zip(seeds, QUEST_MODULI)]

    def decrypt_words(encrypted: bytes) -> bytes:
        # Both the 24-byte header and the body begin on lane zero.
        # The four keys carry over from the header into the body.
        clear = bytearray(len(encrypted))
        for word_index, (word,) in enumerate(struct.iter_unpack("<H", encrypted)):
            lane = word_index % len(keys)
            keys[lane] = keys[lane] * QUEST_MULTIPLIERS[lane] % QUEST_MODULI[lane]
            struct.pack_into("<H", clear, word_index * 2, word ^ keys[lane])
        return bytes(clear)

    header = decrypt_words(read_exact(source, 24))
    payload_bytes, = struct.unpack_from("<I", header)
    # Decrypt only the stated payload length. The sector span can include padding.
    if payload_bytes % 2 or not 0x68 <= payload_bytes <= entry.readable_bytes - 32:
        raise ValueError("Invalid quest payload length")
    payload = decrypt_words(read_exact(source, payload_bytes))
    if payload[4:8] != b"2NDG":
        raise ValueError("Decrypted payload has no 2NDG signature")
    for region, salt in QUEST_HASH_SALTS.items():
        if hashlib.sha1(payload + salt).digest() == header[4:24]:
            return payload, region
    raise ValueError("Quest SHA-1 verification failed")


def quest_fields(entry_id: int, payload: bytes, hash_region: str) -> dict:
    """Turn documented little-endian fields into one export record."""
    return {
        "archive_entry": entry_id,
        "quest_id": struct.unpack_from("<H", payload, 0x64)[0],
        "star_code": payload[0x66],
        "contract_fee_z": struct.unpack_from("<H", payload, 0x50)[0],
        "reward_z": struct.unpack_from("<H", payload, 0x54)[0],
        "ko_deduction_z": struct.unpack_from("<H", payload, 0x58)[0],
        "time_limit_ticks": struct.unpack_from("<I", payload, 0x5C)[0],
        "guild_points": struct.unpack_from("<H", payload, 0x3C)[0],
        "decoded_bytes": len(payload),
        "hash_region": hash_region,
    }


def entry_at(entries: list[ArchiveEntry], entry_id: int) -> ArchiveEntry:
    if not 0 <= entry_id < len(entries):
        raise ValueError(f"Entry ID must be between 0 and {len(entries) - 1}")
    return entries[entry_id]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Path to DATA.BIN")
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help="Write an entry index to CSV")
    index.add_argument("output", type=Path)
    extract = commands.add_parser("extract", help="Copy one stored entry to a file")
    extract.add_argument("entry_id", type=int)
    extract.add_argument("output", type=Path)
    quest = commands.add_parser("quest", help="Decode and verify one quest")
    quest.add_argument("entry_id", type=int)
    quest.add_argument("--raw-output", type=Path, help="Save the verified quest payload")
    quests = commands.add_parser("quests", help="Decode an inclusive range of quest entries to CSV")
    quests.add_argument("first", type=int)
    quests.add_argument("last", type=int)
    quests.add_argument("output", type=Path)
    args = parser.parse_args()

    try:
        with args.archive.open("rb") as source:
            entries = read_index(source)
            if args.command == "index":
                with args.output.open("x", encoding="utf-8", newline="") as output:
                    writer = csv.writer(output)
                    writer.writerow(("entry_id", "byte_offset", "sector_span_bytes", "indexed_payload_bytes"))
                    for entry in entries:
                        writer.writerow((entry.entry_id, entry.byte_offset, entry.sector_span_bytes,
                                         entry.indexed_payload_bytes))
                print(f"Indexed {len(entries)} entries.")
            elif args.command == "extract":
                entry = entry_at(entries, args.entry_id)
                with args.output.open("xb") as output:
                    extract_entry(source, entry, output)
                print(f"Copied {entry.readable_bytes} stored bytes from entry {entry.entry_id}.")
            elif args.command == "quest":
                payload, region = decode_quest(source, entry_at(entries, args.entry_id))
                if args.raw_output is not None:
                    with args.raw_output.open("xb") as output:
                        output.write(payload)
                print(json.dumps(quest_fields(args.entry_id, payload, region), indent=2))
            else:
                entry_at(entries, args.first)
                entry_at(entries, args.last)
                if args.first > args.last:
                    raise ValueError("The last entry must be at or after the first")
                # Verify the whole requested range before creating the CSV.
                rows = []
                for entry in entries[args.first:args.last + 1]:
                    try:
                        payload, region = decode_quest(source, entry)
                    except ValueError as error:
                        raise ValueError(f"Entry {entry.entry_id}: {error}") from error
                    rows.append(quest_fields(entry.entry_id, payload, region))
                with args.output.open("x", encoding="utf-8", newline="") as output:
                    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                print(f"Decoded and verified {len(rows)} quests.")
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
