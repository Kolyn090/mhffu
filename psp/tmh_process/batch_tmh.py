import os
import argparse
from pathlib import Path
from tmh import convert_tmh

def batch_tmh(folder_path, new_save_path):
    folder = Path(folder_path)
    pac_files = list(folder.glob("*.pac"))
    pmo_files = []
    mtl_files = []
    tmh_files = []
    for f in pac_files:
        basename = os.path.basename(f)
        if "0000" in basename:
            pmo_files.append(f)
        elif "0001" in basename:
            mtl_files.append(f)
        elif "0002" in basename:
            tmh_files.append(f)
    for tmh_file in tmh_files:
        basename = os.path.basename(tmh_file).replace("-0002.pac", "")
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
    args = parser.parse_args()

    inputfolder = args.inputfolder
    outputfolder = args.outputfolder

    os.makedirs(outputfolder, exist_ok=True)
    batch_tmh(inputfolder, outputfolder)
