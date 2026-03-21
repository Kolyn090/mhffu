import array
import struct
from logger import Logger, LogStyle

def run_ge(pmo, scale, verbose=False, extra_indent=0):
    Logger.enable = verbose
    file_address = pmo.tell()

    pmo.seek(0, 2)
    size = pmo.tell()
    pmo.seek(file_address)

    if file_address + 4 > size:
        raise ValueError(f"BAD READ: {file_address:08X} + 4 > {size:08X}")
    
    Logger.highlight(f"=== GE START @ {file_address:08X} ===", color=LogStyle.RED, indent=extra_indent)
    
    index_offset = 0
    vertices = []
    faces = []
    vertex_address = None
    index_address = None
    vertex_format = None
    position_trans = None
    normal_trans = None
    color_trans = None
    texture_trans = None
    weight_trans = None
    index_format = None
    face_order = None

    while True:
        Logger.debug(f"[BEFORE READ] pos={pmo.tell():08X}", 1+extra_indent)
        command = array.array('I', pmo.read(4))[0]
        Logger.debug(f"[AFTER READ ] pos={pmo.tell():08X}", 1+extra_indent)

        Logger.debug(f"COMMAND: {' '.join(f'{x:02X}' for x in command.to_bytes(4, 'little'))}", 1+extra_indent)

        command_type = command >> 24
        # NOP - No Operation
        if command_type == 0x00:
            Logger.info("NOP - No Operation: 0x00", 1+extra_indent)
            pass
        # VADDR - Vertex Address (BASE)
        elif command_type == 0x01:
            Logger.info("VADDR - Vertex Address (BASE): 0x01", 1+extra_indent)
            if vertex_address is not None:
                index_offset = len(vertices)
            vertex_address = file_address + (command & 0xffffff)
        # IADDR - Index Address (BASE)
        elif command_type == 0x02:
            Logger.info("IADDR - Index Address (BASE): 0x02", 1+extra_indent)
            index_address = file_address + (command & 0xffffff)
        # PRIM - Primitive Kick
        elif command_type == 0x04:
            Logger.info("PRIM - Primitive Kick: 0x04", 1+extra_indent)
            primative_type = (command >> 16) & 7
            index_count = command & 0xffff
            Logger.info(f"PRIM type={primative_type} count={index_count}", 2+extra_indent)
            Logger.debug(f"VADDR(Vertex Address)={vertex_address:08X} IADDR(Index Address)={index_address:08X}", 2+extra_indent)
            command_address = pmo.tell()
            index = range(len(vertices) - index_offset, len(vertices) + index_count - index_offset)
            Logger.debug(f"indices (len: {len(index)}): {list(index)}", 2+extra_indent)

            if index_format is not None:
                Logger.debug(f"Index Format: {index_format}", 2+extra_indent)
                index = array.array(index_format)
                Logger.debug(f"Index after format: {index}", 2+extra_indent)
                Logger.debug(f"[BEFORE JUMP] pos={pmo.tell():08X}", 2+extra_indent)
                pmo.seek(index_address)
                Logger.debug(f"[AFTER JUMP ] pos={pmo.tell():08X}", 2+extra_indent)
                index.fromfile(pmo, index_count)
                Logger.debug(f"Index after fromfile: {index}", 2+extra_indent)
                index_address = pmo.tell()
                Logger.debug(f"Index Address: {index_address:08X}", 2+extra_indent)

            vertex_size = struct.calcsize(vertex_format)
            Logger.debug(f"vertex_size={vertex_size} format={vertex_format}", 2+extra_indent)
            Logger.debug(f"Vertex Loop Begin:", 2+extra_indent)
            for i in index:
                Logger.highlight(f"[BEFORE JUMP] pos={pmo.tell():08X}", 3+extra_indent)
                pmo.seek(vertex_address + vertex_size * i)
                Logger.highlight(f"[AFTER JUMP ] pos={pmo.tell():08X}", 3+extra_indent)

                raw_bytes = pmo.read(vertex_size)
                raw_vertex = list(struct.unpack(vertex_format, raw_bytes))

                Logger.debug(
                    f"RAW VERTEX: {' '.join(f'{b:02X}' for b in raw_bytes)}",
                    3+extra_indent
                )

                Logger.debug(f"raw_vertex={raw_vertex}", 3+extra_indent)
                Logger.debug(f"Position Trans: {position_trans}", 3+extra_indent)
                Logger.debug(f"Scale: {scale}", 3+extra_indent)

                vertex = {}
                vertex['z'] = (raw_vertex.pop() / position_trans) * scale[2]
                vertex['y'] = (raw_vertex.pop() / position_trans) * scale[1]
                vertex['x'] = (raw_vertex.pop() / position_trans) * scale[0]

                Logger.debug(f"decoded_vertex={vertex}", 3+extra_indent)
                Logger.debug(f"pos=({vertex['x']:.2f},{vertex['y']:.2f},{vertex['z']:.2f})", 3+extra_indent)
                
                Logger.debug(f"raw_vertex={raw_vertex}", 3+extra_indent)

                if normal_trans is not None:
                    Logger.debug(f"Normal Trans: {normal_trans}", 3+extra_indent)

                    vertex['k'] = raw_vertex.pop() / normal_trans
                    vertex['j'] = raw_vertex.pop() / normal_trans
                    vertex['i'] = raw_vertex.pop() / normal_trans

                    Logger.debug(f"normal=({vertex['i']:.2f},{vertex['j']:.2f},{vertex['k']:.2f})", 3+extra_indent)
                    Logger.debug(f"raw_vertex={raw_vertex}", 3+extra_indent)

                if color_trans is not None:
                    raw_vertex.pop() # NOTE: the OBJ format does not support vertex colors
                    Logger.debug(f"raw_vertex={raw_vertex}", 3+extra_indent)

                if texture_trans is not None:
                    vertex['v'] = raw_vertex.pop() / texture_trans
                    vertex['u'] = raw_vertex.pop() / texture_trans
                    Logger.debug(f"uv=({vertex['y']:.2f},{vertex['v']:.2f})", 3+extra_indent)
                    Logger.debug(f"raw_vertex={raw_vertex}", 3+extra_indent)

                if weight_trans is not None:
                    pass # NOTE: the OBJ format does not support vertex weights
                if len(vertices) <= (i + index_offset):
                    vertices.extend([None] * (i + index_offset + 1 - len(vertices)))
                    Logger.debug(f"index[{i}] -> vertex_id={i + index_offset}", 3+extra_indent)
                vertices[i + index_offset] = vertex

            Logger.debug(f"[BEFORE JUMP] pos={pmo.tell():08X}", 1+extra_indent)
            pmo.seek(command_address)
            Logger.debug(f"[AFTER JUMP ] pos={pmo.tell():08X}", 1+extra_indent)

            # r = range(index_count - 2)
            # if primative_type == 3:
            #     Logger.info(f"Primitive mode: {'TRIANGLES' if primative_type == 3 else 'TRIANGLE_STRIP'}", 2)
            #     r = range(0, index_count, 3)
            # elif primative_type != 4:
            #     ValueError('Unsupported primative type: 0x{:02X}'.format(primative_type))
            
            # Logger.debug(f"Face Loop Begin:", 2)
            # for i in r:
            #     face = {'v3': index[i+2] + index_offset}
            #     if i < 5:
            #         Logger.debug(f"face: {face}", 3)
            #     if ((i + face_order) % 2) or ((primative_type == 3) and face_order):
            #         face['v2'] = index[i] + index_offset
            #         face['v1'] = index[i+1] + index_offset
            #     else:
            #         face['v1'] = index[i] + index_offset
            #         face['v2'] = index[i+1] + index_offset
            #     faces.append(face)

            Logger.debug(f"Face Loop Begin:", 2+extra_indent)

            if primative_type == 3:  # TRIANGLES
                for i in range(0, index_count, 3):
                    v0 = index[i] + index_offset
                    v1 = index[i+1] + index_offset
                    v2 = index[i+2] + index_offset

                    faces.append({'v1': v0, 'v2': v1, 'v3': v2})

                    if i < 5:
                        Logger.debug(f"face: {(v0, v1, v2)}", 3+extra_indent)

            elif primative_type == 4:  # TRIANGLE STRIP
                for i in range(index_count - 2):
                    if i % 2 == 0:
                        v0 = index[i] + index_offset
                        v1 = index[i+1] + index_offset
                        v2 = index[i+2] + index_offset
                    else:
                        v0 = index[i+1] + index_offset
                        v1 = index[i] + index_offset
                        v2 = index[i+2] + index_offset

                    faces.append({'v1': v0, 'v2': v1, 'v3': v2})

                    if i < 5:
                        Logger.debug(f"face: {(v0, v1, v2)}", 3+extra_indent)
            else:
                raise ValueError(f'Unsupported primitive type: 0x{primative_type:02X}')
            
            # # TODO: change back
            # return

        # RET - Return from Call
        elif command_type == 0x0b:
            Logger.info("RET - Return from Call: 0x0b", 1+extra_indent)
            break
        # BASE - Base Address Register
        elif command_type == 0x10:
            Logger.info("BASE - Base Address Register: 0x10", 1+extra_indent)
            pass
        # VTYPE - Vertex Type
        elif command_type == 0x12:
            Logger.info("VTYPE - Vertex Type: 0x12", 1+extra_indent)
            vertex_format = ''

            weight = (command >> 9) & 3
            Logger.debug(f"Weight: {weight}", 1+extra_indent)
            if weight != 0:
                count = ((command >> 14) & 7) + 1
                vertex_format += str(count) + (None, 'B', 'H', 'f')[weight]
                weight_trans = (None, 0x80, 0x8000, 1)[weight]
            bypass_transform = (command >> 23) & 1

            texture = command & 3
            Logger.debug(f"Texture: {texture}", 1+extra_indent)
            if texture != 0:
                vertex_format += (None, '2B', '2H', '2f')[texture]
                texture_trans = 1
                if not bypass_transform:
                    texture_trans = (None, 0x80, 0x8000, 1)[texture]

            color = (command >> 2) & 7
            Logger.debug(f"Color: {color}", 1+extra_indent)
            if color != 0:
                vertex_format += (None, None, None, None, 'H', 'H', 'H', 'I')[color]
                color_trans = (None, None, None, None, 'rgb565', 'rgba5', 'rgba4', 'rgba8')[color]
                print('WARNING: This model uses vertex colors.')

            normal = (command >> 5) & 3
            Logger.debug(f"Normal: {normal}", 1+extra_indent)
            if normal != 0:
                vertex_format += (None, '3b', '3h', '3f')[normal] # NOTE: when bypassing transform Z may be unsigned
                normal_trans = 1
                if not bypass_transform:
                    normal_trans = (None, 0x7f, 0x7fff, 1)[normal]

            position = (command >> 7) & 3
            Logger.debug(f"Position: {position}", 1+extra_indent)
            if position != 0:
                if bypass_transform:
                    vertex_format += (None, '2bB', '2hH', '3f')[position] # TODO: handle float Z clamping
                    position_trans = 1
                else:
                    vertex_format += (None, '3b', '3h', '3f')[position]
                    position_trans = (None, 0x7f, 0x7fff, 1)[position]

            Logger.debug(f"Vertex Format: {vertex_format}", 1+extra_indent)

            index_format = (None, 'B', 'H', 'I')[(command >> 11) & 3]
            if (command >> 18) & 7 > 0:
                raise ValueError('Can not handle morphing')

        # ??? - Offset Address (BASE)
        elif command_type == 0x13:
            Logger.info("??? - Offset Address (BASE): 0x13", 1+extra_indent)
            pass
        # ??? - Origin Address (BASE)
        elif command_type == 0x14:
            Logger.info("??? - Origin Address (BASE): 0x14", 1+extra_indent)
            pass
        # FFACE - Front Face Culling Order
        elif command_type == 0x9b:
            Logger.info("FFACE - Front Face Culling Order: 0x9b", 1+extra_indent)
            face_order = command & 1
        else:
            raise ValueError('Unknown GE command: 0x{:02X}'.format(command_type))
        
    return vertices, faces


def create_mesh(obj, offsets, mesh):
    for i in range(len(mesh)):
        v_old = offsets['v']
        vt_old = offsets['vt']
        vn_old = offsets['vn']
        obj.write('usemtl texture{:02d}\n'.format(mesh[i][2]))
        for vertex in mesh[i][0]:
            obj.write('v {x:f} {y:f} {z:f}\n'.format(**vertex))
            offsets['v'] += 1
            if vertex.get('u') is not None:
                obj.write('vt {u:f} {v:f}\n'.format(**vertex))
                offsets['vt'] += 1
            if vertex.get('i') is not None:
                obj.write('vn {i:f} {j:f} {k:f}\n'.format(**vertex))
                offsets['vn'] += 1
        for face in mesh[i][1]:
            obj.write('f {:d}'.format(face['v1'] + v_old))
            if mesh[i][0][face['v1']].get('u') is not None:
                obj.write('/{:d}/'.format(face['v1'] + vt_old))
            else:
                obj.write('//')
            if mesh[i][0][face['v1']].get('i') is not None:
                obj.write('{:d}'.format(face['v1'] + vn_old))
            obj.write(' {:d}'.format(face['v2'] + v_old))
            if mesh[i][0][face['v2']].get('u') is not None:
                obj.write('/{:d}/'.format(face['v2'] + vt_old))
            else:
                obj.write('//')
            if mesh[i][0][face['v2']].get('i') is not None:
                obj.write('{:d}'.format(face['v2'] + vn_old))
            obj.write(' {:d}'.format(face['v3'] + v_old))
            if mesh[i][0][face['v3']].get('u') is not None:
                obj.write('/{:d}/'.format(face['v3'] + vt_old))
            else:
                obj.write('//')
            if mesh[i][0][face['v3']].get('i') is not None:
                obj.write('{:d}'.format(face['v3'] + vn_old))
            obj.write('\n')
