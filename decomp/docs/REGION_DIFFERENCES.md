# Confirmed region differences

The tested English build is North American `ULUS10391` v1.01. The existing JP extraction uses the `ULJM05500` FUComplete archive. The quest checksum label `NA/EU` identifies the salt used by the English quests. A European retail archive and a clean Japanese retail archive have yet to be tested in this audit.

| Source | JP / FUComplete | EN / North America |
| --- | --- | --- |
| Archive index as stored | Readable sector table | Retail outer cipher on sector table and most entries |
| Sector size | 2,048 bytes | 2,048 bytes |
| Indexed entries | 6,602 | 6,657 |
| Item text pack | Entry 15 | English entry 19. Other language packs follow at 20–23. |
| Quest entry range | 4759–5309 | 4791–5341 |
| Quest digest salt | JP | NA/EU |
| `game_sub.ovl` entry and load base | 56, `0x09C14280` | 76, `0x09C19100` |
| Map-to-stage list table | `0x09CDF678` | `0x09CE4808` |
| Fish-kind definitions | `0x09CCE3B0` | `0x09CD3538` |
| Tutorial fish override | `0x09CE03A8` | `0x09CE5538` |
| Stage overlays | 5490–5756 | 5542–5808 |

The existing extraction comparison found that map-to-stage lists, fish definitions and normalized quest gathering results agree across these two archives for the 551 quests compared. Entry numbers, pointers and text were treated as build-specific. This result covers gathering. Monster statistics, equipment, item definitions, vendor inventories and other gameplay tables still need region-specific source checks.

The Japanese decompilation is a structural lead for locating routines. Confirm their English counterparts through code references and representative live values before trusting a field offset or ID mapping. [Japanese decompilation project](https://github.com/tclamb/mhp2g-decomp)
