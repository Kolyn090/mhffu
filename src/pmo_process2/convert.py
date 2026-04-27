"""
Created on Thu Jan 14 22:39:43 2021

@author: AsteriskAmpersand
"""


import construct_plugin as C
from parser import run_ge
from logger import Logger


def load_pmo(pmo_path: str):
    # Adds padding so next section starts at 16-byte boundary
    # 0 ~ 15 bytes
    alignment = C.Struct(
        "pos" / C.Tell,
        "padding" / C.Padding((-C.this.pos)%16)
    )

    # Global file info
    # 56 - 64 bytes
    Header = C.Struct(
        "pmo" / C.Int8ul[4],  # 4
        "ver" / C.Int8ul[4],  # 4
        "filesize" / C.Int32ul,  # 4
        "clippingDistance" / C.Float32l,  # 4
        "scale" / C.Float32l[3],  # 12
        "meshCount" / C.Int16ul,  # 2
        "materialCount" / C.Int16ul,  # 2 (Possibly number of triangle stripes too)
        "meshHeaderOffset" / C.Int32ul,  # 4
        "vertexGroupHeaderOffset" / C.Int32ul,  # 4
        "materialRemapOffset" / C.Int32ul,  # 4
        "unknI10" / C.Int32ul,  # 4
        "materialDataOffset" / C.Int32ul,  # 4
        "meshDataOffset" / C.Int32ul,  # 4
        "padding" / alignment,  # 0 ~ 15
    )

    # Submesh
    # 16 bytes
    VertexGroupHeader = C.Struct(
        "materialOffset" / C.Int8ul,  # 1
        "boneCount" / C.Int8ul,  # 1
        "cumulativeBoneCount" / C.Int16ul,  # 2
        "meshOffset" / C.Int32ul,  # 4
        "vertexOffset" / C.Int32ul,  # 4
        "indexOffset" / C.Int32ul,  # 4
    )

    # Mesh Header
    # 24 bytes
    MeshHeader = C.Struct(
        "uvScale" / C.Float32l[2],  # 8 (Two float values)
        "unkn1" / C.Int8ul[8],  # 8
        "materialCount" / C.Int16ul,  # 2 (Material slots?)
        "cumulativeMaterialCount" / C.Int16ul,  # 2
        "subMeshCount" / C.Int16ul,  # 2
        "cumulativeSubmeshCount" / C.Int16ul,  # 2
        # Jump to global VertexGroupHeader table, use cumulative index to find this mesh’s submeshes 
        # size = subMeshCount * 16 bytes
        "submeshHeaders" / C.Pointer(
            C.this._.header.vertexGroupHeaderOffset +
            C.this.cumulativeSubmeshCount * VertexGroupHeader.sizeof(),
            VertexGroupHeader[C.this.subMeshCount]
        )
    )

    # Map bone indices
    # 2 bytes
    Skeleton = C.Struct(
        "index" / C.Int8ul,  # 1 byte
        "bone" / C.Int8ul,  # 1 byte
    )

    # ? + 16 bytes
    MaterialContent = C.Struct(
        "index" / C.Computed(C.this._index),
        "rgba" / C.Int8ul[4],  # 4
        "rgba2" / C.Int8ul[4],  # 4
        "textureID" / C.Int32sl,  # 4
        "unkn" / C.Int8ul[4],  # 4
    )

    def _skeleton_count(this):
        last_mesh = this.meshHeaders[this.header.meshCount - 1]
        last_sub = last_mesh.submeshHeaders[last_mesh.subMeshCount - 1]
        return last_sub.boneCount + last_sub.cumulativeBoneCount

    PMO = C.Struct(
        "header" / Header,
        "padding0" / alignment,
        "meshHeaders" / MeshHeader[C.this.header.meshCount],
        "padding1" / alignment,
        C.Seek(C.this.header.materialRemapOffset),
        "materialRemapCount" / C.Computed(
        lambda this:
            this.meshHeaders[this.header.meshCount - 1].cumulativeMaterialCount +
            this.meshHeaders[this.header.meshCount - 1].materialCount
        ),
        "materialRemap" / C.Int8ul[C.this.materialRemapCount],
        "padding3" / alignment,
        "skeletonRemapCount" / C.Computed(_skeleton_count),
        "skeleton" / Skeleton[C.this.skeletonRemapCount],
        "padding4" / alignment,
        "materialData" / MaterialContent[C.this.header.materialCount],
        C.Seek(C.this.header.meshDataOffset),
    )

    class weightParser():
        def __init__(self,weightList):
            
            bufferSize = max([w.index for w in weightList])+1 if weightList else 0
            self.boneIds = [-1]*bufferSize
            self.weightIter = iter(weightList)
        def consume(self,count):
            for _ in range(count):
                w = next(self.weightIter)            
                self.boneIds[w.index] = w.bone
        def __iter__(self):
            return iter(self.boneIds)
    
    def ff(num: float):
        padding = " " if num >= 0 else ""
        return f"{padding}{num:.4f}"

    def pretty_head(mesh: tuple):
        verts = mesh[0]
        faces = mesh[1]
        mats = mesh[2]
        scale = mesh[3]
        uv_scale = mesh[4]

        for i in range(min(1, len(verts))):
            v = verts[i]
            pos = v.position
            norm = v.normal
            uv = v.uv
            Logger.debug(f"Vert   {i}/{len(verts)}:")
            if pos is not None:
                Logger.debug(f"Pos    {i}/{len(verts)}: {(ff(pos.x), ff(pos.y), ff(pos.z))}")
            else:
                Logger.error(f"Pos    {i}/{len(verts)} is None!")

            if norm is not None:
                Logger.debug(f"Normal {i}/{len(verts)}: {(ff(norm.x), ff(norm.y), ff(norm.z))}")
            else:
                Logger.error(f"Normal {i}/{len(verts)} is None!")

            # (u, v) = (0.0, 0.0) → bottom-left of texture
            # (u, v) = (1.0, 1.0) → top-right of texture
            if uv is not None:
                Logger.debug(f"UV     {i}/{len(verts)}: {(ff(uv.u), ff(uv.v))}")
            else:
                Logger.error(f"UV     {i}/{len(verts)} is None!")

        for i in range(min(5, len(faces))):
            Logger.debug(f"Face   {i}/{len(faces)}: {str(faces[i])}")

        for i in range(min(5, len(mats))):
            Logger.debug(f"Mat    {i}/{len(mats)}: {str(mats[i])}")

        Logger.debug(f"Scale: {",".join([str(ff(s)) for s in scale])}")
        Logger.debug(f"UV Scale: {",".join([str(ff(s)) for s in uv_scale])}")
        Logger.newline()

    def better_uv(verts: list):
        for i in range(len(verts)):
            v = verts[i]
            uv = v.uv
            if uv is not None:
                Logger.debug(f"UV     {i}/{len(verts)}: {(ff(uv.u), ff(uv.v))}")
            else:
                Logger.error(f"UV     {i}/{len(verts)} is None!")

    meshes = []
    with open(pmo_path, "rb") as file:
        pmo = PMO.parse_stream(file)
        weightData = weightParser(pmo.skeleton)
        count = 0
        for mesh in pmo.meshHeaders:
            verts = []
            faces = []
            materials = []
            for tristripHeader in mesh.submeshHeaders:
                weightData.consume(tristripHeader.boneCount)
                try:
                    matRIx = mesh.cumulativeMaterialCount + tristripHeader.materialOffset
                    matIx = pmo.materialRemap[matRIx]
                    mat = pmo.materialData[matIx]
                except:
                    mat = pmo.materialData[0]
                file.seek(pmo.header.meshDataOffset + tristripHeader.meshOffset)
                v,f = run_ge(file,weightData)
                faces += [tuple(map(lambda x: x + len(verts),face)) for face in f]
                verts += v
                materials += [mat.index for face in f]
            mesh = (verts,faces,materials,pmo.header.scale,mesh.uvScale)
            meshes.append(mesh)
            # Logger.info(f"Mesh {count}:")
            # pretty_head(mesh)
            if count == 7:
                better_uv(verts)
            count += 1
