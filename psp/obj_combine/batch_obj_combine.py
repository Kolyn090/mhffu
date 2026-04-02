import os
import re
import shutil
import argparse
from pathlib import Path

def combine_objs_with_mtl(input_files, output_obj, output_mtl):
    v_offset = 0
    vt_offset = 0
    vn_offset = 0

    combined_obj = []
    combined_mtl = []

    material_map = {}  # old_name -> new_name

    combined_obj.append(f"mtllib {os.path.basename(output_mtl)}\n")

    for file_idx, obj_file in enumerate(input_files):
        base_name = os.path.splitext(os.path.basename(obj_file))[0]
        mtl_file = None

        with open(obj_file, 'r') as f:
            lines = f.readlines()

        # --- find mtllib ---
        for line in lines:
            if line.startswith("mtllib"):
                mtl_file = os.path.join(os.path.dirname(obj_file), line.split()[1].strip())
                break

        # --- load & rename materials ---
        if mtl_file and os.path.exists(mtl_file):
            with open(mtl_file, 'r') as f:
                mtl_lines = f.readlines()

            current_mtl = None
            for line in mtl_lines:
                if line.startswith("newmtl"):
                    old_name = line.split()[1].strip()
                    new_name = f"{base_name}_{old_name}"
                    material_map[(file_idx, old_name)] = new_name
                    combined_mtl.append(f"newmtl {new_name}\n")
                    current_mtl = old_name
                else:
                    combined_mtl.append(line)

        combined_obj.append(f"\n# --- {base_name} ---\n")

        # Count local vertices first
        local_v = sum(1 for l in lines if l.startswith('v '))
        local_vt = sum(1 for l in lines if l.startswith('vt '))
        local_vn = sum(1 for l in lines if l.startswith('vn '))

        for line in lines:
            if line.startswith('v '):
                combined_obj.append(line)
            elif line.startswith('vt '):
                combined_obj.append(line)
            elif line.startswith('vn '):
                combined_obj.append(line)

            elif line.startswith('usemtl'):
                old = line.split()[1].strip()
                new = material_map.get((file_idx, old), old)
                combined_obj.append(f"usemtl {new}\n")

            elif line.startswith('f '):
                parts = line.strip().split()[1:]
                new_face = []

                for part in parts:
                    vals = part.split('/')

                    v = int(vals[0]) + v_offset
                    vt = int(vals[1]) + vt_offset if len(vals) > 1 and vals[1] else None
                    vn = int(vals[2]) + vn_offset if len(vals) > 2 and vals[2] else None

                    if vt is not None and vn is not None:
                        new_face.append(f"{v}/{vt}/{vn}")
                    elif vt is not None:
                        new_face.append(f"{v}/{vt}")
                    elif vn is not None:
                        new_face.append(f"{v}//{vn}")
                    else:
                        new_face.append(f"{v}")

                combined_obj.append("f " + " ".join(new_face) + "\n")

            elif line.startswith(('mtllib')):
                continue  # skip original

            else:
                combined_obj.append(line)

        # update offsets AFTER processing file
        v_offset += local_v
        vt_offset += local_vt
        vn_offset += local_vn

    # --- write outputs ---
    with open(output_obj, 'w') as f:
        f.writelines(combined_obj)

    with open(output_mtl, 'w') as f:
        f.writelines(combined_mtl)

    print(f"Saved: {output_obj}")
    print(f"Saved: {output_mtl}")

def batch_obj_combine(model_folder: str, save_folder: str):
    folder = Path(model_folder)
    obj_files = list(folder.rglob("*.obj"))
    model_paths = set()
    for obj_file in obj_files:
        model_paths.add(os.path.dirname(obj_file))
    model_paths = sorted(list(model_paths))
    
    for model_path in model_paths:
        new_save_path = os.path.join(save_folder, model_path.replace(model_folder, ''))
        texture_path = os.path.join(model_path, "texture")
        folder = Path(model_path)
        obj_files = list(folder.rglob("*.obj"))
        obj_files = [str(p) for p in obj_files]
        if len(obj_files) <= 0:
            continue
        new_combined_obj_name = os.path.basename(obj_files[0])
        new_combined_obj_name = new_combined_obj_name.split('-')
        new_combined_obj_name = '-'.join(new_combined_obj_name[:-1])
        new_combined_obj_name = new_combined_obj_name + ".obj"
        
        new_mtl_name = new_combined_obj_name.replace(".obj", ".mtl")
        
        new_obj_path = os.path.join(new_save_path, new_combined_obj_name)
        new_mtl_path = os.path.join(new_save_path, new_mtl_name)
        new_path_name = os.path.dirname(new_obj_path)
        os.makedirs(new_path_name, exist_ok=True)

        new_texture_path = os.path.join(new_path_name, "texture")
        shutil.copytree(texture_path, new_texture_path, dirs_exist_ok=True)

        combine_objs_with_mtl(obj_files, new_obj_path, new_mtl_path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('model_folder')
    parser.add_argument('savefolder')
    args = parser.parse_args()

    model_folder = args.model_folder
    savefolder = args.savefolder

    os.makedirs(savefolder, exist_ok=True)
    batch_obj_combine(model_folder, savefolder)

if __name__ == "__main__":
    main()
