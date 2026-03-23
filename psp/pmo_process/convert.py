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

    scale = pmo_header[2:5]

    Logger.debug("=== PMO HEADER ===", extra_indent)
    Logger.highlight("1 Unsigned Int", extra_indent)
    Logger.debug(f"[0] file_size    = {unsigned_int_hex(pmo_header[0])}", extra_indent)

    Logger.highlight("4 Floats", extra_indent)
    Logger.debug(f"[1] width?       = {pmo_header[1]}", extra_indent)
    Logger.debug(f"[2-4] size       = {scale}", extra_indent)

    Logger.highlight("2 Unsigned Shorts", extra_indent)
    Logger.debug(f"[5] i-loop len   = {pmo_header[5]}", extra_indent)
    Logger.debug(f"[6] unknown      = {pmo_header[6]}", extra_indent)

    Logger.highlight("8 Unsigned Ints", extra_indent)
    Logger.debug(f"[7] mesh_table   = {unsigned_int_hex(pmo_header[7])}", extra_indent)
    Logger.debug(f"[8] group_table  = {unsigned_int_hex(pmo_header[8])}", extra_indent)
    Logger.debug(f"[9] ?            = {unsigned_int_hex(pmo_header[9])}", extra_indent)
    Logger.debug(f"[10] ?           = {unsigned_int_hex(pmo_header[10])}", extra_indent)
    Logger.debug(f"[11] vertex_buf  = {unsigned_int_hex(pmo_header[11])}", extra_indent)
    Logger.debug(f"[12-14] ?        = {pmo_header[12:15]}", extra_indent)

    Logger.newline()


def debug_mesh_raw(raw_m, extra_indent):
    Logger.debug("=== MESH HEADER (STRUCT HEX) ===", extra_indent)

    offset = 0
    for i in range(2):
        Logger.debug(f"[{i}] {' '.join(f'{b:02X}' for b in raw_m[offset:offset+4])}", extra_indent)
        offset += 4

    for i in range(2):
        Logger.debug(f"[{2+i}] {' '.join(f'{b:02X}' for b in raw_m[offset:offset+4])}", extra_indent)
        offset += 4

    for i in range(4):
        Logger.debug(f"[{4+i}] {' '.join(f'{b:02X}' for b in raw_m[offset:offset+2])}", extra_indent)
        offset += 2

    for i in range(2):
        Logger.debug(f"[{8+i}] {' '.join(f'{b:02X}' for b in raw_m[offset:offset+4])}", extra_indent)
        offset += 4

def debug_mesh_header(mesh_header, extra_indent):
    Logger.debug("=== MESH HEADER ===", extra_indent)
    Logger.highlight("2 Floats", extra_indent)
    Logger.debug(f"[0]  = {mesh_header[0]}", extra_indent)
    Logger.debug(f"[1]  = {mesh_header[1]}", extra_indent)

    Logger.highlight("2 Unsigned Ints", extra_indent)
    Logger.debug(f"[2]  = {mesh_header[2]}", extra_indent)
    Logger.debug(f"[3]  = {mesh_header[3]}", extra_indent)

    Logger.highlight("4 Unsigned Shorts", extra_indent)
    Logger.debug(f"[4]  = {mesh_header[4]}", extra_indent)
    Logger.debug(f"[5]  = {mesh_header[5]}", extra_indent)
    Logger.debug(f"[6]  = {mesh_header[6]} (Length of J-loop)", extra_indent)
    Logger.debug(f"[7]  = {mesh_header[7]}", extra_indent)

    Logger.highlight("2 Unsigned Ints", extra_indent)
    Logger.debug(f"[8]  = {mesh_header[8]}", extra_indent)
    Logger.debug(f"[9]  = {mesh_header[9]}", extra_indent)


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
    for i, val in enumerate(vertex_group_header):
        Logger.debug(f"[{i}]  = {val}", extra_indent)


# =========================
# CORE LOGIC (UNCHANGED)
# =========================

def read_pmo_header(pmo, extra_indent: int):
    raw = pmo.read(0x38)
    pmo_header = struct.unpack('I4f2H8I', raw)
    debug_pmo_header(raw, pmo_header, extra_indent)
    return pmo_header


def read_mesh_header(pmo, offset, extra_indent: int):
    log_seek(pmo, offset, "mesh_header", extra_indent)
    raw = pmo.read(0x20)
    debug_mesh_raw(raw, extra_indent)
    mesh_header = struct.unpack('2f2I4H2I', raw)
    debug_mesh_header(mesh_header, extra_indent)
    return mesh_header


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

def convert_mh2_pmo2(pmo, obj, mtl_file, second=None, verbose=False, enforce_ge_verbose=False):
    Logger.enable = verbose
    # Logger.set_log_file("log.txt")

    Logger.debug(f"Current Pos: {pmo.tell():08X}")

    pmo_header = read_pmo_header(pmo, 0)
    scale = pmo_header[2:5]

    # Avoid long debug info
    has_dbg_ge_once = False

    dirname = os.path.dirname(obj.name)
    basename = os.path.basename(obj.name)
    count = 0

    #        0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20
    jles = [15, 5, 1, 1,11,12, 3, 5, 3, 1, 7, 1,21, 1, 1, 2, 5, 4,26, 2,120]
    mats = [ 3, 1, 1 ,1, 2, 2, 1, 0, 3, 3, 3, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]

    curr_header = -100000
    for i in range(pmo_header[6]):
        # if i >= len(jles):
        #     continue

        Logger.highlight(f"I-Loop ({i+1} / {pmo_header[5]})", 0, color=LogStyle.BRIGHT_MAGENTA)
        mesh = []
        Logger.highlight("Mesh Header: ", indent=1, color=LogStyle.GREEN)
        mesh_header = read_mesh_header(pmo, pmo_header[7], 1)

        # j_len = jles[i]

        for j in range(j_len):
            Logger.highlight(f"J-Loop ({j+1} / {j_len}) in i:{i+1}", 1, color=LogStyle.RED)

            Logger.highlight("Vertex Group Header: ", indent=2, color=LogStyle.GREEN)

            vg_offset = pmo_header[8] + ((mesh_header[7] + count) * 0x10)
            Logger.debug(f"{pmo_header[8]:08X} + (({mesh_header[7]:08X} + {count}) * 0x10)", 2)
            vertex_group_header = read_vertex_group(pmo, vg_offset, 2)

            Logger.highlight("Vertex Data (PMO  ): ", indent=2, color=LogStyle.GREEN)

            log_seek(pmo, pmo_header[11] + (mesh_header[5] + vertex_group_header[0]) * 16, "vertex_data", 2)

            # material = mats[i]

            ge_extra_indent = 0 if enforce_ge_verbose else 3
            ge_verbose = verbose or enforce_ge_verbose

            if has_dbg_ge_once:
                ge_verbose = False

            if second:
                second.seek(vertex_group_header[3])
                mesh.append(run_ge(second, scale, ge_verbose, ge_extra_indent) + (material,))
                has_dbg_ge_once = True
                Logger.enable = verbose
            else:
                raw = vertex_group_header[3]
                Logger.debug(f"Raw (before offset): {raw}", indent=2)
                offset = pmo_header[12] + raw
                test_offset = pmo_header[12] + raw
                Logger.debug(f"{pmo_header[12]:08X} + {raw:08X} = ", indent=2)
                Logger.debug(f"Offset1: {offset:08X}", indent=2)
                Logger.highlight(f" Offset2: {test_offset:08X}", indent=2, color=LogStyle.YELLOW if offset != test_offset else LogStyle.BRIGHT_BLACK)

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
            count += 1

        if mesh:
            offsets = {'v': 1, 'vt': 1, 'vn': 1}
            new_save_path = os.path.join(dirname, basename.replace(".obj", f"-{i}.obj"))
            with open(new_save_path, 'w') as o:
                o.write('mtllib {}\n'.format(mtl_file))
                o.write(f'g mesh{i:02d}\n')
                create_mesh(o, offsets, mesh)
            place_mtl_in_obj(new_save_path, "material.mtl")

def convert_mh2_pmo(pmo, obj, mtl_file, second=None, verbose=False, enforce_ge_verbose=False):
    Logger.enable = verbose
    # Logger.set_log_file("log.txt")

    Logger.debug(f"Current Pos: {pmo.tell():08X}")

    pmo_header = read_pmo_header(pmo, 0)
    scale = pmo_header[2:5]

    # Avoid long debug info
    has_dbg_ge_once = False

    dirname = os.path.dirname(obj.name)
    basename = os.path.basename(obj.name)
    count = 0

    for i in range(pmo_header[6]):
        Logger.highlight(f"I-Loop ({i+1} / {pmo_header[5]})", 0, color=LogStyle.BRIGHT_MAGENTA)
        mesh = []

        Logger.highlight("Mesh Header: ", indent=1, color=LogStyle.GREEN)
        mesh_header = read_mesh_header(pmo, pmo_header[7], 1)

        vtx_idx = []
        while True:
            Logger.highlight("Vertex Group Header: ", indent=2, color=LogStyle.GREEN)
            vg_offset = pmo_header[8] + ((mesh_header[7] + count) * 0x10)
            vertex_group_header = read_vertex_group(pmo, vg_offset, 2)

            new_val = vertex_group_header[0]
            log_seek(pmo, pmo_header[11] + (mesh_header[5] + vertex_group_header[0]) * 16, "vertex_data", 2)

            ge_extra_indent = 0 if enforce_ge_verbose else 3
            ge_verbose = verbose or enforce_ge_verbose

            if has_dbg_ge_once:
                ge_verbose = False

            material = 3

            if len(vtx_idx) == 0 or new_val == vtx_idx[-1]:
                vtx_idx.append(new_val)
                if second:
                    second.seek(vertex_group_header[3])
                    mesh.append(run_ge(second, scale, ge_verbose, ge_extra_indent) + (material,))
                    has_dbg_ge_once = True
                    Logger.enable = verbose
                else:
                    raw = vertex_group_header[3]
                    Logger.debug(f"Raw (before offset): {raw}", indent=2)
                    offset = pmo_header[12] + raw
                    test_offset = pmo_header[12] + raw
                    Logger.debug(f"{pmo_header[12]:08X} + {raw:08X} = ", indent=2)
                    Logger.debug(f"Offset1: {offset:08X}", indent=2)
                    Logger.highlight(f" Offset2: {test_offset:08X}", indent=2, color=LogStyle.YELLOW if offset != test_offset else LogStyle.BRIGHT_BLACK)

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
