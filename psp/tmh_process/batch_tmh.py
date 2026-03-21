import os
import argparse
from pathlib import Path
from tmh import convert_tmh

def batch_tmh(folder_path, new_save_path, tmh1_code, tmh2_code):
    folder = Path(folder_path)
    pac_files = list(folder.glob("*.pac"))
    tmh_ext_files = list(folder.glob("*.tmh"))
    pac_files.extend(tmh_ext_files)
    tmh_files = []
    tmh_files1 = []
    tmh_files2 = []

    for f in pac_files:
        basename = os.path.basename(f)
        if ".tmh" in basename:
            tmh_file.append(f)
        if tmh1_code and tmh1_code in basename:
            tmh_files1.append(f)
        if tmh2_code and tmh2_code in basename:
            tmh_files2.append(f)

    for tmh_file in tmh_files:
        basename = os.path.basename(tmh_file).replace(f".tmh", "")
        # folder
        save_folder_path = os.path.join(new_save_path, basename)
        os.makedirs(save_folder_path, exist_ok=True)
        
        # file
        mtl_path = os.path.join(save_folder_path, "material.mtl")

        try:
            convert_tmh(tmh_file, mtl_path)
        except Exception as e:
            print(f"Failed to process {tmh_file}")

    for tmh_file in tmh_files1:
        basename = os.path.basename(tmh_file).replace(f"-{tmh1_code}.pac", f"-{tmh1_code}")
        # folder
        save_folder_path = os.path.join(new_save_path, basename)
        os.makedirs(save_folder_path, exist_ok=True)
        
        # file
        mtl_path = os.path.join(save_folder_path, "material.mtl")

        try:
            convert_tmh(tmh_file, mtl_path)
        except Exception as e:
            print(f"Failed to process {tmh_file}")

    for tmh_file in tmh_files2:
        basename = os.path.basename(tmh_file).replace(f"-{tmh2_code}.pac", f"-{tmh2_code}")
        # folder
        save_folder_path = os.path.join(new_save_path, basename)
        os.makedirs(save_folder_path, exist_ok=True)
        
        # file
        mtl_path = os.path.join(save_folder_path, "material.mtl")

        try:
            convert_tmh(tmh_file, mtl_path)
        except Exception as e:
            print(f"Failed to process {tmh_file}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('inputfolder')
    parser.add_argument('outputfolder')
    parser.add_argument('--tmh1_code', required=False)
    parser.add_argument('--tmh2_code', required=False)
    args = parser.parse_args()

    inputfolder = args.inputfolder
    outputfolder = args.outputfolder
    tmh1_code = args.tmh1_code
    tmh2_code = args.tmh2_code

    os.makedirs(outputfolder, exist_ok=True)
    batch_tmh(inputfolder, outputfolder, tmh1_code, tmh2_code)
