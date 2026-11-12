# Initial extraction status

This status covers the first audit pass of the English archive. The [database audit](DATABASE_AUDIT.md) gives the validation method and specific source investigation for each file. The [binary source notes](BINARY_SOURCES.md) distinguish verified offsets from unresolved gameplay fields.

| Dataset | Current support | Safe automatic proposal |
| --- | --- | --- |
| `armors.json` | Name-reference checks. gameplay extraction pending | Pending |
| `awards.json` | Schema inventory. binary source pending | Pending |
| `Comrade/skills.json` | Schema inventory. binary source pending | Pending |
| `Comrade/stats.json` | Schema inventory. binary source pending | Pending |
| `Comrade/temperament.json` | Schema inventory. binary source pending | Pending |
| `decorations.json` | Name-reference checks. gameplay extraction pending | Pending |
| `Farm/beehive.json` | Schema inventory. binary source pending | Pending |
| `Farm/bug-catch.json` | Schema inventory. binary source pending | Pending |
| `Farm/bug-tree.json` | Schema inventory. binary source pending | Pending |
| `Farm/casting-machine.json` | Schema inventory. binary source pending | Pending |
| `Farm/cave.json` | Schema inventory. binary source pending | Pending |
| `Farm/farm-renovate.json` | Schema inventory. binary source pending | Pending |
| `Farm/farmfield.json` | Schema inventory. binary source pending | Pending |
| `Farm/fishing-spot.json` | Schema inventory. binary source pending | Pending |
| `Farm/mining-bomb.json` | Schema inventory. binary source pending | Pending |
| `Farm/mining-spot.json` | Schema inventory. binary source pending | Pending |
| `Farm/mushroom-tree.json` | Schema inventory. binary source pending | Pending |
| `Farm/plants-addition.json` | Schema inventory. binary source pending | Pending |
| `Farm/seeds.json` | Schema inventory. binary source pending | Pending |
| `item-notes.json` | Name-reference checks. gameplay extraction pending | Pending |
| `items-combine.json` | Name-reference checks. gameplay extraction pending | Pending |
| `items.json` | English ID and text verified for 1,226 rows. numerical definitions pending | Add IDs for 1,226 rows |
| `Kitchen/meal-effects.json` | Schema inventory. binary source pending | Pending |
| `Kitchen/meals.json` | Schema inventory. binary source pending | Pending |
| `maps.json` | Per-quest spot and fish extraction verified. public map crosswalk pending | Pending |
| `Merchants/merchant-gal.json` | Schema inventory. binary source pending | Pending |
| `Merchants/merchant.json` | Schema inventory. binary source pending | Pending |
| `Merchants/peddling-granny-discount.json` | Schema inventory. binary source pending | Pending |
| `Merchants/peddling-granny.json` | Schema inventory. binary source pending | Pending |
| `Merchants/treshi-disciple.json` | Schema inventory. binary source pending | Pending |
| `Monsters/basic-parts-duration.json` | Name-reference checks. gameplay extraction pending | Pending |
| `Monsters/element-effectiveness.json` | Name-reference checks. gameplay extraction pending | Pending |
| `Monsters/item-effectiveness.json` | Name-reference checks. gameplay extraction pending | Pending |
| `Monsters/knockout-small-monsters.json` | Name-reference checks. gameplay extraction pending | Pending |
| `Monsters/monsters-material.json` | Name-reference checks. gameplay extraction pending | Pending |
| `Monsters/monsters.json` | Schema inventory. binary source pending | Pending |
| `Monsters/size.json` | Name-reference checks. gameplay extraction pending | Pending |
| `Monsters/stats.json` | Name-reference checks. gameplay extraction pending | Pending |
| `Monsters/status-effectiveness.json` | Name-reference checks. gameplay extraction pending | Pending |
| `Monsters/weapon-effectiveness.json` | Name-reference checks. gameplay extraction pending | Pending |
| `npc-dialogue.json` | Schema inventory. binary source pending | Pending |
| `Quests/elder.json` | English quest payloads verified. public linkage and field comparison partial | Pending |
| `Quests/gal-1.json` | English quest payloads verified. public linkage and field comparison partial | Pending |
| `Quests/gal-2.json` | English quest payloads verified. public linkage and field comparison partial | Pending |
| `Quests/gal-3.json` | English quest payloads verified. public linkage and field comparison partial | Pending |
| `Quests/nekoht.json` | English quest payloads verified. public linkage and field comparison partial | Pending |
| `Quests/training-1.json` | English quest payloads verified. public linkage and field comparison partial | Pending |
| `Quests/training-2.json` | English quest payloads verified. public linkage and field comparison partial | Pending |
| `Quests/training-3.json` | English quest payloads verified. public linkage and field comparison partial | Pending |
| `Quests/training-group.json` | English quest payloads verified. public linkage and field comparison partial | Pending |
| `Quests/treasure-hunt.json` | English quest payloads verified. public linkage and field comparison partial | Pending |
| `skills.json` | Schema inventory. binary source pending | Pending |
| `trenya.json` | Schema inventory. binary source pending | Pending |
| `veggie_elder.json` | Schema inventory. binary source pending | Pending |
| `Weapons/ammo.json` | Schema inventory. binary source pending | Pending |
| `Weapons/bows.json` | Schema inventory. binary source pending | Pending |
| `Weapons/rapid-shot.json` | Schema inventory. binary source pending | Pending |
| `Weapons/sharpness.json` | Schema inventory. binary source pending | Pending |
| `Weapons/shelling.json` | Schema inventory. binary source pending | Pending |
| `Weapons/weapons-craft.json` | Name-reference checks. gameplay extraction pending | Pending |
| `Weapons/weapons.json` | Schema inventory. binary source pending | Pending |

## Reproduce the audit

Run from the existing decomp project root. The last positional argument must be a new report directory. To check another revision, supply that revision's checkout and SHA.

```powershell
py -B scripts\audit_database.py 'E:\Archive\mhfu-db' 'E:\Games\MH2G Game\En_DATA\DATA.BIN' output\audit-rerun --revision 98144e264350d6dcd0db25ba7c27eded49838547 --gathering output\en\gathering.json
```

The script checks the exact source archive hash and parses the database in read-only mode. It writes inventory, raw English item and quest values, comparisons, the optional gathering cross-check, and an additive item proposal under the report directory.
