"""Inspect FUComplete and English MHFU DATA.BIN archives and decode 2NDG quests."""

import argparse
import csv
import hashlib
import json
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator


SECTOR_BYTES = 2048
CHUNK_BYTES = 1024 * 1024
# Byte substitution table for the PSP DATA.BIN cipher documented by mhef.
DATA_DECODE_TABLE = bytes.fromhex(
    "cb9685a65f3eab0350b79c5cb240eff6ff611529a2f1ec523528d9682436c474"
    "26e2d58c474d2cfa8666c14f0b815b1bc00afd17a4a96d63adf3f46e8d8914dd"
    "59874a30cefe3f7e0649a5045ed0dee80fd4131fbab969713de4dc5890343a3"
    "cca1076c7c84533c3921d2b1c8f6f0507385751d6da2db3c62e64321e43b15d"
    "e1bb8e9d7277f227c97f9eaa6a2f6cf948e7a00956b8bd2041cd9580d7230c"
    "42e5ae8b7dbc5439bf650188e07bb616184bcc225ab5ebfcf89b4ee6a8be677"
    "397940062b4d221251182db9302847cd3b0a391a7f755707a08758a5379fb9f"
    "46f583d80ee9ed12d1dff0372a44199a31cfa1afe33b1a4c78c260ee986b0d"
    "99eac5ac"
)
EN_CLEAR_ENTRIES = {42: b"~SCE", 43: b"~SCE", **dict.fromkeys(range(46, 63), b"PSMF")}
QUEST_MODULI = (0xFF9D, 0xFFA9, 0xFFC7, 0xFFF1)
QUEST_MULTIPLIERS = (0x1709, 0x3DF3, 0x747B, 0xB381)
QUEST_HASH_SALTS = {"JP": b"37wyS2Jfc3x5w9oG", "NA/EU": b"Vd6gh8F30wA86Ex5"}


@dataclass(frozen=True)
class ArchiveEntry:
    entry_id: int
    byte_offset: int
    sector_span_bytes: int
    indexed_payload_bytes: int | None
    outer_encrypted: bool = False

    @property
    def readable_bytes(self) -> int:
        if self.indexed_payload_bytes is not None:
            return self.indexed_payload_bytes
        return self.sector_span_bytes


class QuestChecksumError(ValueError):
    """A quest signature was found, but the embedded SHA-1 did not verify."""


class ArchiveCipher:
    """Decode one file's stream, seeded by its start sector (zero for the index)."""

    def __init__(self, sector: int):
        self.high = (sector >> 16) or 0x2345
        self.low = (sector & 0xFFFF) or 0x7F8D

    def decode(self, encrypted: bytes) -> bytes:
        high, low = self.high, self.low
        clear = bytearray(len(encrypted))
        for offset, (word,) in enumerate(struct.iter_unpack("<I", encrypted.translate(DATA_DECODE_TABLE))):
            high = (high * 0x2345) % 0xFFD9
            low = (low * 0x7F8D) % 0xFFF1
            struct.pack_into("<I", clear, offset * 4, word ^ (high << 16 | low))
        self.high, self.low = high, low
        return bytes(clear)


def read_exact(source: BinaryIO, count: int) -> bytes:
    data = source.read(count)
    if len(data) != count:
        raise ValueError("Unexpected end of file")
    return data


def read_index(source: BinaryIO) -> list[ArchiveEntry]:
    """Read sector offsets and optional exact sizes from a clear or encrypted index."""
    archive_bytes = source.seek(0, os.SEEK_END)
    source.seek(0)
    first_word = read_exact(source, 4)
    first_sector, = struct.unpack("<I", first_word)
    index_bytes = first_sector * SECTOR_BYTES
    if archive_bytes % SECTOR_BYTES:
        raise ValueError("DATA.BIN size is not aligned to 2,048-byte sectors")
    encrypted = not SECTOR_BYTES <= index_bytes < archive_bytes
    if encrypted:
        first_sector, = struct.unpack("<I", ArchiveCipher(0).decode(first_word))
        index_bytes = first_sector * SECTOR_BYTES
    if not SECTOR_BYTES <= index_bytes < archive_bytes:
        raise ValueError("Expected a DATA.BIN with a valid clear or encrypted sector index")
    source.seek(0)
    header = read_exact(source, index_bytes)
    if encrypted:
        header = ArchiveCipher(0).decode(header)
    words = [value for (value,) in struct.iter_unpack("<I", header)]
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
    if encrypted:
        # Identify the international layout by its unencrypted module and movie signatures.
        for entry_id, signature in EN_CLEAR_ENTRIES.items():
            if entry_id >= len(spans) or spans[entry_id] < len(signature):
                raise ValueError("Unsupported encrypted DATA.BIN layout")
            source.seek(offsets[entry_id] * SECTOR_BYTES)
            if read_exact(source, len(signature)) != signature:
                raise ValueError(f"Unsupported encrypted DATA.BIN layout at entry {entry_id}")
    return [
        ArchiveEntry(entry_id, start * SECTOR_BYTES, spans[entry_id], sizes.get(entry_id),
                     encrypted and entry_id not in EN_CLEAR_ENTRIES)
        for entry_id, start in enumerate(offsets[:-1])
    ]


def entry_chunks(source: BinaryIO, entry: ArchiveEntry, length: int) -> Iterator[bytes]:
    if not 0 <= length <= entry.readable_bytes:
        raise ValueError(f"Read exceeds entry {entry.entry_id}")
    source.seek(entry.byte_offset)
    cipher = ArchiveCipher(entry.byte_offset // SECTOR_BYTES) if entry.outer_encrypted else None
    while length:
        count = min(length, CHUNK_BYTES)
        # Outer encryption works on words. Any final padding is inside the entry's sector span.
        data = read_exact(source, (count + 3) & ~3 if cipher else count)
        yield cipher.decode(data)[:count] if cipher else data
        length -= count


def read_entry_data(source: BinaryIO, entry: ArchiveEntry, length: int | None = None) -> bytes:
    """Read an entry or prefix with only the outer archive encryption removed."""
    return b"".join(entry_chunks(source, entry, entry.readable_bytes if length is None else length))


def extract_entry(source: BinaryIO, entry: ArchiveEntry, output: BinaryIO) -> None:
    """Extract one entry in chunks without loading the whole entry into memory."""
    for chunk in entry_chunks(source, entry, entry.readable_bytes):
        output.write(chunk)


def decode_quest(source: BinaryIO, entry: ArchiveEntry) -> tuple[bytes, str]:
    """Unwrap one encrypted quest and verify its payload before returning it."""
    if entry.readable_bytes < 40:
        raise ValueError("Quest entry is too small for its header")
    prefix = read_entry_data(source, entry, 40)
    seeds = struct.unpack("<4H", prefix[:8])
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

    header = decrypt_words(prefix[8:32])
    payload_bytes, = struct.unpack_from("<I", header)
    # Decrypt only the stated payload length. The sector span can include padding.
    if payload_bytes % 2 or not 0x68 <= payload_bytes <= entry.readable_bytes - 32:
        raise ValueError("Invalid quest payload length")
    first_payload_words = decrypt_words(prefix[32:])
    if first_payload_words[4:8] != b"2NDG":
        raise ValueError("Decrypted payload has no 2NDG signature")
    # The first eight bytes are also a whole number of four-lane rounds.
    payload = first_payload_words + decrypt_words(read_entry_data(source, entry, 32 + payload_bytes)[40:])
    for region, salt in QUEST_HASH_SALTS.items():
        if hashlib.sha1(payload + salt).digest() == header[4:24]:
            return payload, region
    raise QuestChecksumError(f"Quest SHA-1 verification failed for entry {entry.entry_id}")


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
    extract = commands.add_parser("extract", help="Extract one entry and remove any outer archive encryption")
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
                print(f"Extracted {entry.readable_bytes} bytes from entry {entry.entry_id}.")
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
