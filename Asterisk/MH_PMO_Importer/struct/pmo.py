# -*- coding: utf-8 -*-
"""
Created on Thu Jan 14 22:39:43 2021

@author: AsteriskAmpersand
"""
#import construct as C
try:
    from .pmo_parse import run_ge
    from .. import construct_plugin as C
except:
    from pmo_parse import run_ge
    import construct as C
    #from pmo_parse_orig import run_ge
    pass

# Reads current file position
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
    "submeshHeaders" / C.Pointer(C.this._.header.vertexGroupHeaderOffset + 
                                 C.this.cumulativeSubmeshCount*VertexGroupHeader.sizeof(),
                                 VertexGroupHeader[C.this.subMeshCount]) 
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

PMO = C.Struct(
    "header" / Header,
    "padding0" / alignment,
    "meshHeaders" / MeshHeader[C.this.header.meshCount],
    "padding1" / alignment,
    C.Seek(C.this.header.materialRemapOffset),
    "materialRemapCount" / C.Computed(lambda this: this.meshHeaders[this.header.meshCount-1].cumulativeMaterialCount + this.meshHeaders[this.header.meshCount-1].materialCount),
    "materialRemap" / C.Int8ul[C.this.materialRemapCount],
    "padding3" / alignment,
    "skeletonRemapCount" / C.Computed(lambda this: this.meshHeaders[this.header.meshCount-1].submeshHeaders[this.meshHeaders[this.header.meshCount-1].subMeshCount-1].boneCount+
                                                  this.meshHeaders[this.header.meshCount-1].submeshHeaders[this.meshHeaders[this.header.meshCount-1].subMeshCount-1].cumulativeBoneCount),
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

def load_pmo(pmopath):
    meshes = []
    with open(pmopath,"rb") as inf:
        pmo = PMO.parse_stream(inf)
        weightData = weightParser(pmo.skeleton)
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
                inf.seek(pmo.header.meshDataOffset + tristripHeader.meshOffset)
                #DEBUG = []
                v,f = run_ge(inf,weightData)
                faces += [tuple(map(lambda x: x + len(verts),face)) for face in f]
                verts += v
                materials += [mat.index for face in f]
            meshes.append((verts,faces,materials,pmo.header.scale,mesh.uvScale))
    return meshes,pmo

def load_cmo(cmopath):
    meshes = []
    verts = []
    faces = []
    with open(cmopath,"rb") as inf:
        cmoflag = inf.read(1)
        v,f = run_ge(inf,[0 for i in range(8)])
        faces += [tuple(map(lambda x: x + len(verts),face)) for face in f]
        verts += v
        meshes.append((verts,faces,[],[1,1,1],[1,1]))
    return meshes,cmoflag

if __name__ in "__main__":
    from pathlib import Path
    for file in Path(r"D:\Downloads\em37\models\models").rglob("*.pmo"):
        #print(file)
        meshes,pmo = load_pmo(file)
        an = False
        for ix,mat in enumerate(pmo.materialData):
            if tuple(mat.unkn) != (0,0,0,0):
                if not an: print(file.replace(r"D:\Downloads\em37\models"+"\\",""))
                print("%d:%s"%(ix,tuple(mat.unkn)))
                an = True