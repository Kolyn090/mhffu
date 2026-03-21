import os
import re
import shutil
import argparse
from pathlib import Path

def organize_obj_mtl(ofp, tfp, new_save_path):
    folder = Path(ofp)
    obj_files = list(folder.glob("*.obj"))

    for obj_file in obj_files:
        basename = os.path.basename(obj_file)
        name = basename.replace(".obj", "")

        save_folder_path = os.path.join(new_save_path, name)
        os.makedirs(save_folder_path, exist_ok=True)

        # Copy OBJ
        new_obj_path = os.path.join(save_folder_path, basename)
        shutil.copy(obj_file, new_obj_path)

        # ✅ Fix mtllib
        with open(new_obj_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        text = re.sub(r"^mtllib\s+.*$", "mtllib material.mtl", text, flags=re.MULTILINE)

        with open(new_obj_path, "w", encoding="utf-8") as f:
            f.write(text)

        # Copy texture folder
        target_mtl_folder = os.path.join(tfp, name)
        texture_dest = os.path.join(save_folder_path, "texture")

        if os.path.exists(target_mtl_folder):
            shutil.copytree(target_mtl_folder, texture_dest, dirs_exist_ok=True)

            # ✅ Move .mtl OUT of texture folder
            for file in os.listdir(texture_dest):
                if file.endswith(".mtl"):
                    src_mtl = os.path.join(texture_dest, file)
                    dst_mtl = os.path.join(save_folder_path, "material.mtl")

                    shutil.move(src_mtl, dst_mtl)
                    break  # assume only one .mtl

            # ✅ (IMPORTANT) Fix texture paths inside .mtl
            mtl_path = os.path.join(save_folder_path, "material.mtl")
            if os.path.exists(mtl_path):
                with open(mtl_path, "r", encoding="utf-8", errors="ignore") as f:
                    mtl_text = f.read()

                # Force textures to use relative path
                mtl_text = re.sub(
                    r"(map_Kd\s+)(.*)",
                    r"\1texture/\2",
                    mtl_text
                )

                with open(mtl_path, "w", encoding="utf-8") as f:
                    f.write(mtl_text)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pmo_folder')
    parser.add_argument('tmh_folder')
    parser.add_argument('savefolder')
    args = parser.parse_args()

    pmo_folder = args.pmo_folder
    tmh_folder = args.tmh_folder
    savefolder = args.savefolder

    os.makedirs(savefolder, exist_ok=True)
    organize_obj_mtl(pmo_folder, tmh_folder, savefolder)
