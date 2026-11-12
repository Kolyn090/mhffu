# Verified binary sources

## English archive and index

The input was the 772,732,928-byte `E:\Games\MH2G Game\En_DATA\DATA.BIN` from North American MHFU `ULUS10391` v1.01. SHA-256 is `d7e5b5cebe07fe00ae1167ed6779f8a6d246ffe35842878a1aeadbee48ac89f5`. This hash was checked during the audit and previously matched the DATA.BIN in the local disc image.

The raw first four bytes, `D6 E3 69 A0`, read as a little-endian sector number of 2,691,294,166. The original parser treated that word as a plaintext sector pointer and rejected it because it lay beyond the file. Deciphering the index gives first sector 17, a monotonic index of 6,657 entries, and terminal sector 377,311 at EOF. Both builds use 2,048-byte sectors. The English index has 813 supplemental exact lengths. The existing shared decoder applies the retail outer cipher to the index with seed zero and to encrypted entries with their start sector as seed. The cipher uses a byte substitution and two rolling keys. EN entries 42–43 (`~SCE`) and 46–62 (`PSMF`) are stored clear. The audit reuses that decoder. [Retail PSP cipher reference](https://github.com/IncognitoMan/mhef/blob/master/mhef/psp.py)

## Item text

Entry 19 has a 23-group offset directory starting at byte 8. Group offsets are relative to the pack. Group 1 spans bytes 35,993–59,102 and holds names. Group 2 spans bytes 59,103–146,762 and holds descriptions. Both start with a 5,048-byte table of 1,261 little-endian group-relative string offsets followed by `0xFFFFFFFF`. Strings are NUL-terminated UTF-8. Retain control codes and line breaks in the raw extraction. Slot 0 is the dummy item. Text slots 1–1260 serve as item IDs, corroborated by quest loot and fish outcome IDs, including Honey (161), Insect Husk (246), Knife Mackerel (229), and Kut-Ku Scale (382). The gathering export agrees with the string table for all 351 item IDs it uses.

Rarity, stack limit, sale price, icon, color, and recipe mechanics remain unresolved. The next source to verify is the item definition array used by item lookups in the English executable or overlays. Cross-reference several IDs with different visible values to establish record stride, offsets and units. Trace the combine menu's ingredient and result lookups to the recipe table before comparing rates and quantities.

## Quest records

Archive entries 4791–5341 have the inner four-lane quest cipher and decode to a payload with `2NDG` at byte 4. All 551 pass SHA-1 of the clear payload plus the decoder's `NA/EU` salt, checked against each quest's stored digest. A one-bit change in the checksum for entry 4791, made in memory, raised `QuestChecksumError`. The audit uses this entry range for the hash-pinned build.

| Payload source | Meaning |
| --- | --- |
| `u32(0x00)` | Visual block offset |
| `u32(visual + 0x04)`, `u32(visual + 0x08)`, `u32(visual + 0x0C)` | Contract fee, base reward, faint deduction, in zenny |
| `u32(visual + 0x10)` | Time ticks. The audit compares using 1,800 ticks per minute, supported by the matching published time values. |
| `u32(visual + 0x14)` | Language directory offset. First pointer leads to six payload-relative offsets for English title, goal, failure, details, displayed monster text and client. |
| `u16(visual + 0x18)`, `u8(visual + 0x1A)`, `u8(visual + 0x1C)` | Internal quest ID, raw star code, map ID |
| `u8(0x44)` | Raw rank code |
| `u32(0x14)`, `u32(0x18)` | Large and small spawn configuration pointers used by the spawn extractor |
| `u32(0x1C)`, `u32(0x24)` | Quest area gathering and loot pointers |

Display text, spawn configurations and completion logic are separate sources. The public `main-monsters` array needs a documented rule that accounts for all three. Menu lists and unlock logic remain to be traced before certifying quest folder assignment, difficulty or progression. Training loadout data and treasure-specific rules also remain to be traced.

## Maps, gathering and placements

Entry 76 is `game_sub.ovl`, identified by the `MWo3` signature and embedded name. It loads at `0x09C19100`. Map-to-stage lists are at `0x09CE4808`, fish-kind definitions at `0x09CD3538`, and the tutorial fishing override at `0x09CE5538`. Entries 5542–5808 are the 267 stage overlays, identified by embedded `stageNNN.ovl` names. `extract_gathering.py` resolves a quest's engine area slot to a stage, reads its `<4f4H` gathering nodes through the `x = -1.0` terminator, resolves loot by node parameters, and uses rank-specific stage fish tables or the tutorial override for fishing. Fish weights describe nominal spawn probabilities. Bait and catch behavior need their own analysis. Quest data excludes Pokke Farm.

The current gather export joins against all 551 newly decoded quest headers on archive entry, quest ID, map ID, and rank code. Its 19,995 spot rows cover 29 quest map variants. Quest 1 (entry 4791, map 11) illustrates the join. Area slot 1 resolves to stage 92, where gathering spot 2 can yield Honey (161) at 65% nominal weight. Area slot 7 resolves to stage 99, with Knife Mackerel (229) at 20% nominal fish-spawn weight for fish spot 0. Public map names, displayed area numbers, rank labels and grouped material lists still need their own crosswalk.

`extract_monster_spawns.py` and `extract_map_placements.py` provide complementary extracts in `output/en/`. Spawn data helps trace quest monsters and modifiers. Render placement data is outside the current database audit.
