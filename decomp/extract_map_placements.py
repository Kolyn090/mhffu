"""Export stage draw placements and, optionally, Forest and Hills grass patches."""

import argparse
import hashlib
import json
import math
import struct
import sys
from collections import defaultdict
from pathlib import Path

from decode_mhfu import read_index
from extract_gathering import read_entry, read_maps, u16, u32


DRAW_COMMAND = struct.Struct("<4BI")
DRAW_DESCRIPTOR = struct.Struct("<hhII")
STAGE_COUNT = 267
STAGE_OVERLAY_BASE = 5490
STAGE_PAC_BASE = 5756

# Four standalone grass textures identified visually in the Forest and Hills TMHs.
# The same artwork can have a different texture index in different stages.
GRASS_TEXTURES = {
    "b11bc9d9016940383763edc33c85a15bbadb8b8dda6dd7201952e55e7810fc57",
    "879cf8351c4c56b075bf00adaa9e55d255d47c92ce06386810ae2c7b4146bfed",
    "7370635855c30286321abbedf8da6a2cdb138e1961fa389c0d51ee2bb572c6db",
    "524a61046f59b6b8bbdac82881b317521dc93b2162b31b8bfe074ac3b1f7efe0",
}
BAKED_MESH_OPS = {1, 6, 7, 11}
STATIC_TRANSLATION_OPS = {3, 4, 5, 9, 10, 12}
PLACED_OPS = STATIC_TRANSLATION_OPS | {2, 8, 13, 14, 16, 17}


def xyz(data, offset):
    result = struct.unpack_from("<3f", data, offset)
    if not all(map(math.isfinite, result)):
        raise ValueError(f"Invalid position at {offset:#x}")
    return result


def scalar(data, offset):
    value, = struct.unpack_from("<f", data, offset)
    if not math.isfinite(value):
        raise ValueError(f"Invalid float at {offset:#x}")
    return value


def draw_lists(overlay, base, text_size, memory_size):
    """Locate the stage's constant draw-descriptor getter in MIPS text."""
    text_end = 64 + text_size
    candidates = {}
    for offset in range(64, text_end - 8, 4):
        first, second, third = struct.unpack_from("<3I", overlay, offset)
        # lui v0, hi; jr ra; addiu v0, v0, lo (signed delay-slot immediate).
        if (first >> 16, second, third >> 16) != (0x3C02, 0x03E00008, 0x2442):
            continue
        low = (third & 0x7FFF) - (third & 0x8000)
        descriptor = ((first & 0xFFFF) << 16) + low - base
        if not text_end <= descriptor <= len(overlay) - DRAW_DESCRIPTOR.size:
            continue
        model_count, prop_count, model_ptr, prop_ptr = DRAW_DESCRIPTOR.unpack_from(overlay, descriptor)
        if not (0 < model_count <= 64 and 0 <= prop_count <= 128):
            continue
        lists = []
        for name, count, address in (("terrain", model_count, model_ptr), ("props", prop_count, prop_ptr)):
            if count == 0 and address == 0:
                continue
            start = address - base
            end = start + DRAW_COMMAND.size * count
            if not count or not text_end <= start <= end <= len(overlay):
                break
            commands = list(DRAW_COMMAND.iter_unpack(overlay[start:end]))
            if any(not 1 <= opcode <= 19 or flags > 15 or (
                parameter and not base <= parameter < base + memory_size
            ) for opcode, flags, _, _, parameter in commands):
                break
            lists.append((name, start, commands))
        else:
            candidates[descriptor] = lists
    if len(candidates) > 1:
        raise ValueError("Ambiguous stage draw descriptor")
    return next(iter(candidates.values()), [])


def placements(overlay, base, opcode, parameter):
    """Read placement parameters used by the standard StageBase draw routines."""
    if opcode in BAKED_MESH_OPS:
        return {"placement_kind": "mesh_geometry"}
    if opcode not in PLACED_OPS and opcode != 15:
        return {"placement_kind": "stage_specific"}
    offset = parameter - base
    if not 0 <= offset <= len(overlay) - 12:
        return {"placement_kind": "runtime_parameters"}
    if opcode == 15:
        count, far, near, cutoff, address = struct.unpack_from("<hBBfI", overlay, offset)
        start = address - base
        if not (count >= 0 and 0 <= start <= len(overlay) - 16 * count and math.isfinite(cutoff)):
            raise ValueError("Invalid list of repeated draw positions")
        return {
            "placement_kind": "repeated",
            "near_mesh_index": near, "far_mesh_index": far, "clip_cutoff": cutoff,
            "positions_xyz": [xyz(overlay, start + 16 * index) for index in range(count)],
        }

    position_offset = offset if opcode in {3, 12} else offset + 0x10
    record = {
        "placement_kind": "placed" if opcode in STATIC_TRANSLATION_OPS else "animated_anchor",
        "position_xyz": xyz(overlay, position_offset),
    }
    if opcode in {4, 5, 10, 17}:
        axes = u16(overlay, offset)
        record["rotation_axis"] = next(
            (axis for bit, axis in ((1, "x"), (2, "y"), (4, "z")) if axes & bit), None
        )
        record["rotation_radians"] = scalar(overlay, offset + (4 if opcode in {4, 5} else 8))
    if opcode == 5:
        record["scale_xyz"] = xyz(overlay, offset + 0x20)
    if opcode == 12:
        record["visibility_min_xyz"] = xyz(overlay, offset + 0x10)
        record["visibility_max_xyz"] = xyz(overlay, offset + 0x20)
    if opcode == 13:
        record["motion_amplitude_xyz"] = xyz(overlay, offset + 0x20)
    return record


def stage_commands(overlay, stage_id):
    base, text_size, data_size, bss_size = struct.unpack_from("<4I", overlay, 8)
    name = overlay[32:64].split(b"\0")[0]
    if overlay[:4] != b"MWo3" or name != f"stage{stage_id:03}.ovl".encode("ascii"):
        raise ValueError(f"Unexpected overlay for stage {stage_id}")
    if 64 + text_size > len(overlay):
        raise ValueError(f"Truncated overlay text for stage {stage_id}")
    commands = []
    for model, start, records in draw_lists(overlay, base, text_size, 64 + text_size + data_size + bss_size):
        for index, (opcode, flags, alpha, mesh, parameter) in enumerate(records):
            commands.append({
                "model": model, "command_index": index,
                "command_offset": start + index * DRAW_COMMAND.size,
                "opcode": opcode, "flags": flags, "alpha_threshold": alpha,
                "mesh_index": mesh, "parameter_offset": parameter - base if parameter else None,
                **placements(overlay, base, opcode, parameter),
            })
    return commands


def pac_member(pac, index):
    if index >= u32(pac, 0):
        return b""
    offset, length = struct.unpack_from("<II", pac, 4 + 8 * index)
    if offset == 0:
        return b""
    if not 0 <= offset <= len(pac) - length:
        raise ValueError(f"Invalid stage PAC member {index}")
    return pac[offset:offset + length]


def connected_patches(groups):
    """Group triangles sharing decoded vertex positions within a texture and mesh."""
    parents = {}

    def root(vertex):
        while parents[vertex] != vertex:
            parents[vertex] = parents[parents[vertex]]
            vertex = parents[vertex]
        return vertex

    for group in groups:
        vertices = [
            (vertex["x"], vertex["y"], vertex["z"]) if vertex is not None else None
            for vertex in group.vertices
        ]
        for face in group.faces:
            points = [vertices[face[key]] for key in ("v1", "v2", "v3")]
            if None in points or len(set(points)) != 3:
                continue
            for point in points:
                parents.setdefault(point, point)
            first, second, third = map(root, points)
            parents[second] = first
            parents[third] = first
    islands = defaultdict(list)
    for point in parents:
        islands[root(point)].append(point)
    return islands.values()


def transform_vertex(point, command, anchor):
    """Apply the same axis rotation, axis scale and translation as StageBase."""
    x, y, z = point
    axis = command.get("rotation_axis")
    if axis:
        cosine = math.cos(command["rotation_radians"])
        sine = math.sin(command["rotation_radians"])
        if axis == "x":
            y, z = cosine * y - sine * z, sine * y + cosine * z
        elif axis == "y":
            x, z = cosine * x + sine * z, -sine * x + cosine * z
        else:
            x, y = cosine * x - sine * y, sine * x + cosine * y
    scale = command.get("scale_xyz", (1, 1, 1))
    return tuple(value * factor + translation for value, factor, translation in zip((x, y, z), scale, anchor))


def grass_patches(pac, commands, pmo, tmh):
    textures = {
        texture["index"] for texture in tmh.decode_tmh(pac_member(pac, 1))
        if hashlib.sha256(texture["rgba"]).hexdigest() in GRASS_TEXTURES
    }
    if not textures:
        return [], []
    parts = {}
    for name, member in (("terrain", 0), ("props", 2)):
        blob = pac_member(pac, member)
        if not blob:
            continue
        grouped = defaultdict(list)
        for group in pmo.parse(blob).mesh_groups:
            texture = group.material & 0xFF
            if texture in textures:
                grouped[group.mesh_record, texture].append(group)
        parts[name] = [(mesh, texture, connected_patches(groups))
                       for (mesh, texture), groups in grouped.items()]

    patches = []
    unresolved = []
    for command in commands:
        kind = command["placement_kind"]
        mesh_index = command.get("near_mesh_index", command["mesh_index"])
        for mesh, texture, islands in parts.get(command["model"], []):
            if mesh != mesh_index:
                continue
            if kind == "mesh_geometry":
                anchors = [(0, 0, 0)]
            elif kind == "placed":
                anchors = [command["position_xyz"]]
            elif kind == "repeated":
                anchors = command["positions_xyz"]
            else:
                unresolved.append({"command_offset": command["command_offset"],
                                   "mesh_index": mesh, "texture_index": texture})
                continue
            for instance, anchor in enumerate(anchors):
                for island_index, vertices in enumerate(islands):
                    positions = [transform_vertex(vertex, command, anchor) for vertex in vertices]
                    axes = list(zip(*positions))
                    lower, upper = list(map(min, axes)), list(map(max, axes))
                    patches.append({
                        "command_offset": command["command_offset"], "model": command["model"],
                        "mesh_index": mesh, "texture_index": texture, "instance_index": instance,
                        "mesh_patch_index": island_index, "vertex_count": len(vertices),
                        "bounds_min_xyz": lower, "bounds_max_xyz": upper,
                        "estimated_base_xyz": [(lower[0] + upper[0]) / 2, lower[1], (lower[2] + upper[2]) / 2],
                    })
    return patches, unresolved


def extract(archive, formats_tools):
    if formats_tools is not None:
        sys.path.insert(0, str(formats_tools.resolve()))
        from mhfu_model import pmo, tmh

    with archive.open("rb") as source:
        entries = read_index(source)
        game_sub = read_entry(source, entries[56])
        base = u32(game_sub, 8)
        if game_sub[32:44] != b"game_sub.ovl" or base != 0x09C14280:
            raise ValueError("Expected the ULJM05500 game_sub overlay at entry 56")
        maps = read_maps(game_sub, base)
        forest = set(maps[2]["stage_ids_by_area_index"] + maps[16]["stage_ids_by_area_index"])
        stages = {}
        for stage_id in range(STAGE_COUNT):
            overlay_id = STAGE_OVERLAY_BASE + stage_id
            pac_id = STAGE_PAC_BASE + stage_id if stage_id else None
            try:
                commands = stage_commands(read_entry(source, entries[overlay_id]), stage_id)
                record = {"overlay_entry": overlay_id, "base_pac_entry": pac_id, "draw_commands": commands}
                if formats_tools is not None and stage_id in forest:
                    pac = read_entry(source, entries[pac_id])
                    record["grass_patches"], record["unresolved_grass_commands"] = grass_patches(
                        pac, commands, pmo, tmh
                    )
            except (ValueError, IndexError, struct.error) as error:
                raise ValueError(f"Stage {stage_id}: {error}") from error
            stages[stage_id] = record
    return {
        "archive_base_disc_id": "ULJM05500", "maps": maps, "stages": stages,
        "notes": {
            "coordinates": "Stage-space XYZ in game units. Use the map's stage list to resolve area indices.",
            "mesh_geometry": "The draw command has no separate object origin. Placement is in the model's vertices.",
            "animated_anchor": "Stored reference position. Runtime movement, rotation or scaling can change the rendered geometry.",
            "runtime_parameters": "The command has no position data stored in the overlay file.",
            "stage_specific": "Custom draw behavior. Mesh index is the stored command field and may not identify the final rendered geometry.",
            "grass_patches": "Connected geometry using four visually identified standalone grass textures in Forest and Hills. "
                             "Estimated bases are bounds-derived, and one tuft can span multiple patches. "
                             "Mixed texture atlases, ground texture paint and quest gathering props are outside this pass.",
            "scope": "Base stage draw data. Quest-specific props, collision shapes and runtime-only geometry are outside this export.",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--formats-tools", type=Path,
                        help="Path to MHFU-ModKit/formats/tools for optional Forest grass mesh analysis")
    args = parser.parse_args()
    try:
        result = extract(args.archive, args.formats_tools)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            output.write("\n")
    except (OSError, ImportError, ValueError, IndexError, struct.error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Exported {len(result['stages'])} stage overlays.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
