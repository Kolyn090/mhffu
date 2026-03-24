import os
import struct
from logger import Logger, LogStyle
from base import run_ge, create_mesh

import sys
sys.path.append(os.path.abspath("../organize_process"))
from replace_mtl import place_mtl_in_obj  # type: ignore

def log_seek(pmo, target, label, indent=0):
    before = pmo.tell()
    Logger.highlight(f"[BEFORE JUMP {label}] pos={before:08X}", indent)

    pmo.seek(target)

    after = pmo.tell()
    delta = after - before

    if delta > 0:
        direction = "FORWARD"
    elif delta < 0:
        direction = "BACKWARD"
    else:
        direction = "STAY"

    Logger.highlight(
        f"[AFTER  JUMP {label}] pos={after:08X} | Δ={delta:+} (0x{delta:+X}) ({direction})",
        indent
    )

def unsigned_int_hex(val):
    hex_bytes = struct.pack('<I', val)
    return ' '.join(f'{b:02X}' for b in hex_bytes)

# =========================
# DEBUG HELPERS
# =========================

def debug_pmo_header(raw, pmo_header, extra_indent):
    offset = 0
    Logger.debug("=== PMO HEADER (STRUCT HEX) ===")

    Logger.debug(f"[0] {' '.join(f'{b:02X}' for b in raw[offset:offset+4])}", extra_indent)
    offset += 4

    for i in range(4):
        Logger.debug(f"[{1+i}] {' '.join(f'{b:02X}' for b in raw[offset:offset+4])}", extra_indent)
        offset += 4

    for i in range(2):
        Logger.debug(f"[{5+i}] {' '.join(f'{b:02X}' for b in raw[offset:offset+2])}", extra_indent)
        offset += 2

    for i in range(8):
        Logger.debug(f"[{7+i}] {' '.join(f'{b:02X}' for b in raw[offset:offset+4])}", extra_indent)
        offset += 4

    Logger.debug("=== PMO HEADER ===", extra_indent)
    Logger.highlight("1 Unsigned Int", extra_indent)
    Logger.debug(f"[0]  file_size                                = {unsigned_int_hex(pmo_header[0])}", extra_indent)

    Logger.highlight("4 Floats", extra_indent)
    Logger.highlight(f" [1] width?                                    = {pmo_header[1]} (unused)", extra_indent, color=LogStyle.BRIGHT_BLACK)
    Logger.debug(f"[2] size x                                    = {pmo_header[2]}", extra_indent)
    Logger.debug(f"[3] size y                                    = {pmo_header[3]}", extra_indent)
    Logger.debug(f"[4] size z                                    = {pmo_header[4]}", extra_indent)

    Logger.highlight("2 Unsigned Shorts", extra_indent)
    Logger.highlight(f" [5] No idea                                   = {pmo_header[5]} (unused)", extra_indent, color=LogStyle.BRIGHT_BLACK)
    Logger.highlight(f" [6] i-loop len                                = {pmo_header[6]} (unused)", extra_indent, color=LogStyle.BRIGHT_BLACK)
    hint1 = "↑ Note: use determine_i_len() instead"
    Logger.debug(hint1, extra_indent)

    Logger.highlight("8 Unsigned Ints", extra_indent)
    Logger.debug(f"[7]  Mesh Table begin (0x20)  = {unsigned_int_hex(pmo_header[7])}", extra_indent)
    Logger.debug(f"[8]  Vertex group header begin = {unsigned_int_hex(pmo_header[8])}", extra_indent)
    hint2 = "↑ Note: each vertex group header is 0x10, the last vertex group header should be directly above pmo_header[9]"
    Logger.debug(hint2, extra_indent)
    Logger.debug(f"[9] Material index map table begin (I think?) = {unsigned_int_hex(pmo_header[9])}", extra_indent)
    Logger.highlight(f" [10] Material index map table end (I think?)   = {unsigned_int_hex(pmo_header[10])}", extra_indent, color=LogStyle.BRIGHT_BLACK)
    Logger.debug(f"[11] Material index table  = {unsigned_int_hex(pmo_header[11])}", extra_indent)
    Logger.debug(f"[12] Begin of the first GE region              = {unsigned_int_hex(pmo_header[12])}", extra_indent)
    Logger.highlight(f" [13] Trash?                                    = {pmo_header[13]} (unused)", extra_indent, color=LogStyle.BRIGHT_BLACK)
    Logger.highlight(f" [14] Trash?                                    = {pmo_header[14]} (unused)", extra_indent, color=LogStyle.BRIGHT_BLACK)

    Logger.newline()

def debug_vertex_group_raw(raw_v, extra_indent):
    Logger.debug("=== Vertex Group HEADER (STRUCT HEX) ===", extra_indent)

    offset = 0
    for i in range(2):
        Logger.debug(f"[{i}] {' '.join(f'{b:02X}' for b in raw_v[offset:offset+1])}", extra_indent)
        offset += 1

    Logger.debug(f"[2] {' '.join(f'{b:02X}' for b in raw_v[offset:offset+2])}", extra_indent)
    offset += 2

    for i in range(3):
        Logger.debug(f"[{i+3}] {' '.join(f'{b:02X}' for b in raw_v[offset:offset+4])}", extra_indent)
        offset += 4

def debug_vertex_group_header(vertex_group_header, extra_indent):
    Logger.debug("=== Vertex Group HEADER ===", extra_indent)

    Logger.highlight("2 Unsigned Chars", extra_indent)
    Logger.debug(f"[1] Vertex group flag (?) = {vertex_group_header[1]}", extra_indent)
    Logger.highlight(f" [2] No idea               = {vertex_group_header[2]} (unused)", extra_indent, color=LogStyle.BRIGHT_BLACK)

    Logger.highlight("1 Unsigned Short", extra_indent)
    Logger.highlight(f" [3] No idea               = {vertex_group_header[3]} (unused)", extra_indent, color=LogStyle.BRIGHT_BLACK)

    Logger.highlight("3 Unsigned Ints", extra_indent)
    Logger.debug(f"[4] Vertex offset         = {vertex_group_header[4]}", extra_indent)
    hint1 = "↑ Note: add pmo_header[12] is the GE region"
    Logger.debug(hint1, extra_indent)
    Logger.highlight(f" [5] No idea               = {vertex_group_header[5]} (unused)", extra_indent, color=LogStyle.BRIGHT_BLACK)

# =========================
# CORE LOGIC
# =========================

def read_pmo_header(pmo, extra_indent: int):
    raw = pmo.read(0x38)
    pmo_header = struct.unpack('I4f2H8I', raw)
    debug_pmo_header(raw, pmo_header, extra_indent)
    return pmo_header

def read_vertex_group(pmo, offset, extra_indent: int):
    log_seek(pmo, offset, "vertex_group_header", extra_indent)
    raw = pmo.read(0x10)
    debug_vertex_group_raw(raw, extra_indent)
    header = struct.unpack('2BH3I', raw)
    debug_vertex_group_header(header, extra_indent)
    return header


# =========================
# MAIN FUNCTION
# =========================

def determine_i_len(pmo, pmo_header):
    vertex_raw_bytes = int((pmo_header[9] - pmo_header[8]))
    pmo.seek(pmo_header[8])
    data = pmo.read(vertex_raw_bytes)
    width = 16
    count = 0
    last = -10000
    for i in range(0, len(data), width):
        chunk = data[i:i+width]
        if chunk:  # avoid empty
            if last != chunk[0]:
                count += 1
                last = chunk[0]
    return count

def convert_mh2_pmo(pmo, mtl_file, dirname, basename, second=None, verbose=False, enforce_ge_verbose=False):
    Logger.enable = verbose
    # Logger.set_log_file("log.txt")

    Logger.debug(f"Current Pos: {pmo.tell():08X}")

    pmo_header = read_pmo_header(pmo, 0)
    scale = pmo_header[2:5]

    # Avoid long debug info
    has_dbg_ge_once = False

    count = 0
    number_of_mesh = determine_i_len(pmo, pmo_header)

    # Each i loop should produce a mesh (part of the model)
    for i in range(number_of_mesh):
        Logger.highlight(f"I-Loop ({i+1} / {pmo_header[6]})", 0, color=LogStyle.BRIGHT_MAGENTA)
        mesh = []

        Logger.highlight("Mesh Header: ", indent=1, color=LogStyle.GREEN)

        # Merge GE runs according to the flag in vertex group header[0]
        vtx_idx = []
        while True:
            Logger.highlight("Vertex Group Header: ", indent=2, color=LogStyle.GREEN)
            vg_offset = pmo_header[8] + (count * 0x10)
            vertex_group_header = read_vertex_group(pmo, vg_offset, 2)

            pmo.seek(pmo_header[9])
            indices_num = 16*int(number_of_mesh/16+1)  # Some of them are trailing zeros, don't count
            
            mat_indices = struct.unpack(f"{indices_num}B", pmo.read(indices_num))
            mat_index = mat_indices[vertex_group_header[0]]
            pmo.seek(pmo_header[11] + (mat_index) * 16)
            # !!! This is not the correct way to get material index
            # Do this for now as I have no clue how to get it +
            # it is not that important to me
            material = struct.unpack('4I', pmo.read(16))[2]

            flag = vertex_group_header[0]

            # ==================================
            # Not important debug info
            ge_extra_indent = 0 if enforce_ge_verbose else 3
            ge_verbose = verbose or enforce_ge_verbose
            if has_dbg_ge_once:
                ge_verbose = False
            ge_verbose = False
            # ==================================

            if len(vtx_idx) == 0 or flag == vtx_idx[-1]:
                vtx_idx.append(flag)
                if second:
                    second.seek(vertex_group_header[3])
                    mesh.append(run_ge(second, scale, ge_verbose, ge_extra_indent) + (material,))
                    has_dbg_ge_once = True
                    Logger.enable = verbose
                else:
                    raw = vertex_group_header[3]
                    offset = pmo_header[12] + raw
                    Logger.debug(f"Now you are in GE region: {pmo_header[12]:08X} + {raw:08X} (Vertex offset) = {offset:08X}", indent=2)

                    Logger.highlight("Vertex Data (GE   ): ", indent=2, color=LogStyle.GREEN)

                    if offset > pmo_header[0]:
                        Logger.highlight(f"Offset TOO LARGE, abort!", indent=2, color=LogStyle.RED)
                        break

                    log_seek(pmo, offset, "vertex_data", 2)
                    try:
                        result = run_ge(pmo, scale, ge_verbose, ge_extra_indent)
                        has_dbg_ge_once = True
                        Logger.enable = verbose

                        if not result:
                            Logger.warn(f"Empty GE at mesh {i}, group {count}", 1)
                            break
                        
                        mesh.append(result + (material,))
                    except Exception as e:
                        Logger.warn(f"Stopping mesh {i}, group {count}: {e}", 1)
                        break
            else:
                break
            count += 1

        if mesh:
            offsets = {'v': 1, 'vt': 1, 'vn': 1}
            new_save_path = os.path.join(dirname, basename.replace(".obj", f"-{i}.obj"))
            with open(new_save_path, 'w') as o:
                o.write('mtllib {}\n'.format(mtl_file))
                o.write(f'g mesh{i:02d}\n')
                create_mesh(o, offsets, mesh)
            place_mtl_in_obj(new_save_path, "material.mtl")
        else:
            Logger.error(f"Failed to process mesh for index {i}")

def convert_mh3_pmo(pmo, obj, second=None):
    offsets = {'v': 1, 'vt': 1, 'vn': 1}
    pmo_header = struct.unpack('I4f2H8I', pmo.read(0x38))
    for i in range(pmo_header[5]):
        mesh = []
        obj.write('g mesh{:02d}\n'.format(i))
        pmo.seek(pmo_header[7] + i * 0x30)
        mesh_header = struct.unpack('8f2I4H', pmo.read(0x30))
        scale = mesh_header[:3]
        for j in range(mesh_header[12]):
            pmo.seek(pmo_header[8] + ((mesh_header[13] + j) * 0x10))
            vertex_group_header = struct.unpack('2BH3I', pmo.read(0x10))
            pmo.seek(pmo_header[11] + (mesh_header[11] + vertex_group_header[0]) * 16)
            material = struct.unpack('4I', pmo.read(16))[2]
            if second:
                second.seek(vertex_group_header[3])
                mesh.append(run_ge(second, scale) + (material,))
            else:
                pmo.seek(pmo_header[12] + vertex_group_header[3])
                mesh.append(run_ge(pmo, scale) + (material,))
        create_mesh(obj, offsets, mesh)
