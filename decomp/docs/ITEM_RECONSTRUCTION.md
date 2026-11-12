# English item and combination reconstruction

This run uses the North American ULUS10391 v1.01 disc. DATA.BIN inside the disc image has the same SHA-256 as the standalone archive. DATA.BIN supplies the English strings. The matching disc's clear MIPS executable, `/PSP_GAME/SYSDIR/BOOT.BIN`, supplies item and recipe definitions. A scan of all decoded archive entries found neither of the two tested definition-table fingerprints. The generator requires both files and checks both digests.

The Japanese decompilation supplied structure and symbol names. English offsets, pointer resolution, table counts, and output values were verified from the English binaries. [Structure definitions](https://github.com/tclamb/mhp2g-decomp/blob/development/include/item_manager.hpp) · [Item and mix routines](https://github.com/tclamb/mhp2g-decomp/blob/development/src/eboot/item_manager.cpp)

## Items

Entry 19 in DATA.BIN contains names in group 1 and descriptions in group 2. The internal ID is the common slot in these tables and the item definition array. There are 1,261 slots. The raw export includes the name and description byte offsets within entry 19 and the definition offset within BOOT.BIN for every ID.

| Public field | English source and conversion |
| --- | --- |
| `name`, `description` | UTF-8 in entry 19. Join display lines, preserving explicit hyphens and control sequences. The raw text is exported separately. |
| `rare` | BOOT.BIN item record +0x02, unsigned byte. The item display in entry 76 loads it at `0x09C2B2CC` and adds one at `0x09C2B2D8`. |
| `carry-max` | Record +0x03, unsigned byte. The English inventory code tests for `0xFF`. Use the public string `Infinity` for that sentinel and integers for other values. |
| `icon`, `color` | Record +0x05 and +0x06, unsigned bytes. The English rendering code reads both fields. The generated JSON translates these IDs into the existing project's presentation vocabulary. The IDs are available in the raw export. |
| `selling-price` | Record +0x10, unsigned little-endian 32-bit sell value in zenny. The English sale code loads this field at `0x08848AA8`. The raw export also keeps the distinct value at +0x0C. |

BOOT.BIN is at ISO sector 54,704. The item array starts at file offset `0x19B86C` (runtime `0x0899D2B8`) and has a 24-byte stride. The binary catalog generated 1,244 named records and retained 17 placeholders in the raw dump. Existing item rows match by unique normalized English name and description. For duplicate names, the only published row with a complete matching record can be linked. The other occurrence remains unresolved.

The comparison linked 1,242 public rows and records 208 sale-price differences, 133 carry-limit differences, and 15 rarity differences. For example, Flash Bomb's stack cap is 5 and Armor Pill's sale value is 260z. The report also records presentation differences and two whitespace-only description changes. `generated/items.json` is an English catalog with the public fields and additive integer IDs. It has no published replacement status because it cannot carry every old row through the ID join. `item-changes.json` contains the row-by-row changes and all unresolved originals. The separate `item-updates.patch.json` contains tested replacements for the 1,242 linked rows. All test operations precede replacement operations, and the patch leaves unresolved rows and array positions intact.

Two named English records are absent from the published item catalog. ID 128 is **No Coating**, with the coating item type and unlimited sentinel. ID 875 is **Wyvern**, with the supply flag and transport item type. Both are in the English catalog and listed for review as additions.

The unresolved rows include alternate published versions of Gravibiscus and Celeb Cicada, plus the 15 rows below. The corresponding Japanese slots were checked against entry 15 of the local Japanese archive and the named definitions in the Japanese decompilation. The English name and description at each of these IDs are both `dummy`. These identities explain the regional mismatch and supply no English names or descriptions for a replacement. [Japanese item definitions](https://github.com/tclamb/mhp2g-decomp/blob/development/src/eboot/item_manager.item_definitions.inc.cpp)

| Internal ID | Published name |
| ---: | --- |
| 91 | Polytan Bomb |
| 92 | JUMP Barrel Bomb |
| 518 | Amezari Shell |
| 519 | Amezari Carapace |
| 929 | Famitsu Ticket |
| 930 | Famitsu Invoice |
| 931 | Famitsu PT Tckt |
| 932 | FamitsuCustomTkt |
| 933 | Dengeki Ticket |
| 934 | Dengeki G Ticket |
| 935 | Dengeki 2G Tckt |
| 936 | Dengeki Maoh Tkt |
| 937 | Pirate J Ticket |
| 938 | Pirate J Tckt G |
| 939 | Magazine Ticket |

## Combinations

| BOOT.BIN offset | Table |
| --- | --- |
| `0x1A2EA4` | 172 ten-byte definitions. Second ingredient ID at +0, result ID at +2, rate index at +4, quantity index at +5, recipe ID at +6, flags at +7, alternate index at +8. |
| `0x1A355C` | 1,261 pairs of one-byte count and first definition index. The slot identifies the first ingredient. All 172 definitions are covered exactly once. |
| `0x1A3F38` | 172 displayed ingredient pairs in combination-book order and a `FFFF FFFF` terminator. Each unordered pair joins to one definition. The displayed order supplies `materialA` and `materialB`. |
| `0x1A4208`, `0x1A4224` | Quantity pointers and maximum quantities. A pointed record starts with the minimum and lists per-quantity weights that sum to 100. |
| `0x1A422C` | Seven base success percentages. The English recipe routine reads the rate index at `0x0885BEE4` and the rate at `0x0885BEF4`. The public chance field is the base rate before bonuses. |

Flag bit 0 selects alchemy. The seven assembled treasure recipes have both reveal bits set and a result flagged as treasure. The remaining combinations use the public `normal` label. The candidate has the original seven fields, all 172 rows in repository order, and the same values as the published file. The source export also records ingredient and result IDs, recipe IDs, flags, and quantity weights. [Recipe table structure and index](https://github.com/tclamb/mhp2g-decomp/blob/development/src/eboot/item_manager.mix_definitions.inc.cpp)

## Reproduce

Run from the decomp project. Choose a fresh output directory for each run.

```powershell
$archive = 'E:\Games\MH2G Game\En_DATA\DATA.BIN'
$iso = 'E:\Games\MH2G Game\1840 - Monster Hunter Freedom Unite (USA) (En,Fr,De,Es,It).iso'
$database = 'E:\Archive\mhfu-db'
py -B scripts\reconstruct_items.py $archive $iso $database output\en\reconstruction-rerun
py -B scripts\test_reconstruct_items.py $archive $iso $database
```

[Source map](output/en/reconstruction/source-map.json) · [Item changes and unresolved rows](output/en/reconstruction/item-changes.json) · [Recipe changes](output/en/reconstruction/recipe-changes.json)
