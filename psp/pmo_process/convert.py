import struct
from logger import Logger, LogStyle
from base import run_ge, create_mesh

debug = True

def dbg_seek(pmo, offset, label, indent:int):
    pmo.seek(0, 2)
    size = pmo.tell()
    Logger.debug(f"[SEEK {label}] {offset:08X} / size {size:08X}", indent)
    # if offset >= size:
    #     raise ValueError(f"BAD SEEK {label}: {offset:08X} >= {size:08X}")
    Logger.empty(f"[jump] pos={offset:08X}", indent)
    pmo.seek(offset)

def unsigned_int_hex(val):
    hex_bytes = struct.pack('<I', val)
    return ' '.join(f'{b:02X}' for b in hex_bytes)

# =========================
# DEBUG HELPERS
# =========================

def debug_pmo_header(raw, pmo_header):
    offset = 0
    Logger.debug("=== PMO HEADER (STRUCT HEX) ===")

    Logger.debug(f"[0] {' '.join(f'{b:02X}' for b in raw[offset:offset+4])}", 1)
    offset += 4

    for i in range(4):
        Logger.debug(f"[{1+i}] {' '.join(f'{b:02X}' for b in raw[offset:offset+4])}", 1)
        offset += 4

    for i in range(2):
        Logger.debug(f"[{5+i}] {' '.join(f'{b:02X}' for b in raw[offset:offset+2])}", 1)
        offset += 2

    for i in range(8):
        Logger.debug(f"[{7+i}] {' '.join(f'{b:02X}' for b in raw[offset:offset+4])}", 1)
        offset += 4

    scale = pmo_header[2:5]

    Logger.debug("=== PMO HEADER ===", 0)
    Logger.highlight("1 Unsigned Int", 1)
    Logger.debug(f"[0] file_size    = {unsigned_int_hex(pmo_header[0])}", 1)

    Logger.highlight("4 Floats", 1)
    Logger.debug(f"[1] width?       = {pmo_header[1]}", 1)
    Logger.debug(f"[2-4] size       = {scale}", 1)

    Logger.highlight("2 Unsigned Shorts", 1)
    Logger.debug(f"[5] i-loop len   = {pmo_header[5]}", 1)
    Logger.debug(f"[6] unknown      = {pmo_header[6]}", 1)

    Logger.highlight("8 Unsigned Ints", 1)
    Logger.debug(f"[7] mesh_table   = {unsigned_int_hex(pmo_header[7])}", 1)
    Logger.debug(f"[8] group_table  = {unsigned_int_hex(pmo_header[8])}", 1)
    Logger.debug(f"[9] ?            = {unsigned_int_hex(pmo_header[9])}", 1)
    Logger.debug(f"[10] ?           = {unsigned_int_hex(pmo_header[10])}", 1)
    Logger.debug(f"[11] vertex_buf  = {unsigned_int_hex(pmo_header[11])}", 1)
    Logger.debug(f"[12-14] ?        = {pmo_header[12:15]}", 1)

    Logger.newline()


def debug_mesh_header(raw_m, mesh_header):
    Logger.debug("=== MESH HEADER (STRUCT HEX) ===", 1)

    offset = 0
    for i in range(2):
        Logger.debug(f"[{i}] {' '.join(f'{b:02X}' for b in raw_m[offset:offset+4])}", 2)
        offset += 4

    for i in range(2):
        Logger.debug(f"[{2+i}] {' '.join(f'{b:02X}' for b in raw_m[offset:offset+4])}", 2)
        offset += 4

    for i in range(4):
        Logger.debug(f"[{4+i}] {' '.join(f'{b:02X}' for b in raw_m[offset:offset+2])}", 2)
        offset += 2

    for i in range(2):
        Logger.debug(f"[{8+i}] {' '.join(f'{b:02X}' for b in raw_m[offset:offset+4])}", 2)
        offset += 4

    Logger.debug("=== MESH HEADER ===", 1)
    Logger.highlight("2 Floats", 2)
    Logger.debug(f"[0]  = {mesh_header[0]}", 2)
    Logger.debug(f"[1]  = {mesh_header[1]}", 2)

    Logger.highlight("2 Unsigned Ints", 2)
    Logger.debug(f"[2]  = {mesh_header[2]}", 2)
    Logger.debug(f"[3]  = {mesh_header[3]}", 2)

    Logger.highlight("4 Unsigned Shorts", 2)
    Logger.debug(f"[4]  = {mesh_header[4]}", 2)
    Logger.debug(f"[5]  = {mesh_header[5]}", 2)
    Logger.debug(f"[6]  = {mesh_header[6]} (Length of J-loop)", 2)
    Logger.debug(f"[7]  = {mesh_header[7]}", 2)

    Logger.highlight("2 Unsigned Ints", 2)
    Logger.debug(f"[8]  = {mesh_header[8]}", 2)
    Logger.debug(f"[9]  = {mesh_header[9]}", 2)


def debug_vertex_group(raw_v, vertex_group_header):
    Logger.debug("=== Vertex Group HEADER (STRUCT HEX) ===", 2)

    offset = 0
    for i in range(2):
        Logger.debug(f"[{i}] {' '.join(f'{b:02X}' for b in raw_v[offset:offset+1])}", 3)
        offset += 1

    Logger.debug(f"[2] {' '.join(f'{b:02X}' for b in raw_v[offset:offset+2])}", 3)
    offset += 2

    for i in range(3):
        Logger.debug(f"[{i+3}] {' '.join(f'{b:02X}' for b in raw_v[offset:offset+4])}", 3)
        offset += 4

    Logger.debug("=== Vertex Group HEADER ===", 2)
    for i, val in enumerate(vertex_group_header):
        Logger.debug(f"[{i}]  = {val}", 3)


# =========================
# CORE LOGIC (UNCHANGED)
# =========================

def read_pmo_header(pmo):
    raw = pmo.read(0x38)
    pmo_header = struct.unpack('I4f2H8I', raw)
    debug_pmo_header(raw, pmo_header)
    return pmo_header


def read_mesh_header(pmo, offset):
    dbg_seek(pmo, offset, "mesh_header", 0)
    raw = pmo.read(0x20)
    mesh_header = struct.unpack('2f2I4H2I', raw)
    debug_mesh_header(raw, mesh_header)
    return mesh_header


def read_vertex_group(pmo, offset):
    dbg_seek(pmo, offset, "vertex_group_header", 0)
    raw = pmo.read(0x10)
    header = struct.unpack('2BH3I', raw)
    debug_vertex_group(raw, header)
    return header


# =========================
# MAIN FUNCTION
# =========================

def convert_mh2_pmo(pmo, obj, second=None):
    Logger.enable = debug
    # Logger.set_log_file("log.txt")
    offsets = {'v': 1, 'vt': 1, 'vn': 1}

    Logger.debug(f"Current Pos: {pmo.tell():08X}")

    pmo_header = read_pmo_header(pmo)
    scale = pmo_header[2:5]

    for i in range(pmo_header[5]):
        Logger.highlight(f"I-Loop ({i+1} / {pmo_header[5]})", 0, color=LogStyle.RED)

        mesh = []
        obj.write(f'g mesh{i:02d}\n')

        Logger.info("Mesh Header: ", end='', indent=1)
        mesh_header = read_mesh_header(pmo, pmo_header[7] + i * 0x20)

        if mesh_header[6] == 0:
            Logger.debug("Continue: mesh_header[6] is 0!", indent=1)
            continue

        for j in range(mesh_header[6]):
            Logger.highlight(f"J-Loop ({j+1} / {mesh_header[6]}) in {i}", 1, color=LogStyle.RED)

            Logger.highlight("Vertex Group Header: ", end='', indent=2, color=LogStyle.GREEN)

            vg_offset = pmo_header[8] + ((mesh_header[7] + j) * 0x10)
            vertex_group_header = read_vertex_group(pmo, vg_offset)

            Logger.info("Vertex Data (PMO  ): ", end='', indent=2)
            dbg_seek(pmo, pmo_header[11] + (mesh_header[5] + vertex_group_header[0]) * 16, "vertex_data", 0)

            material = struct.unpack('4I', pmo.read(16))[2]

            if second:
                second.seek(vertex_group_header[3])
                mesh.append(run_ge(second, scale, False, 3) + (material,))
                Logger.enable = debug
            else:
                raw = vertex_group_header[3]
                Logger.debug(f"Raw (before offset): {raw}", indent=2)
                offset = pmo_header[12] + raw
                test_offset = pmo_header[12] + raw
                Logger.debug(f"Offset1: {offset}", indent=2)
                Logger.highlight(f" Offset2: {test_offset}", indent=2, color=LogStyle.YELLOW if offset != test_offset else Logger.BRIGHT_BLACK)

                Logger.info("Vertex Data (GE   ): ", end='', indent=2)
                dbg_seek(pmo, offset, "vertex_data", 0)

                try:
                    result = run_ge(pmo, scale, False, 3)
                    Logger.enable = debug
                    if not result:
                        Logger.warn(f"Empty GE at mesh {i}, group {j}", 1)
                        break

                    mesh.append(result + (material,))
                except Exception as e:
                    Logger.warn(f"Stopping mesh {i}, group {j}: {e}", 1)
                    break

        # TODO: change back
        create_mesh(obj, offsets, mesh)

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
