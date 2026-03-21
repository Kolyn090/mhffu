import os
import argparse
from pmo import convert_pmo
from pathlib import Path

debug = False

def is_valid_pmo(path):
    with open(path, 'rb') as f:
        header = f.read(8)
        return header.startswith(b'pmo\x00')

def batch_pmo(folder_path, new_save_path):
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
    for pmo_file, mtl_file in zip(pmo_files, mtl_files):
        if not is_valid_pmo(pmo_file):
            print(f"Skipping non-PMO: {pmo_file}")
            continue
        basename = os.path.basename(pmo_file).replace("-0000.pac", ".obj")
        save_file_path = os.path.join(new_save_path, basename)
        try:
            convert_pmo(pmo_file, mtl_file, save_file_path)
        except Exception as e:
            print(f"Failed to process {pmo_file}")
            if debug:
                print(f"File size: {os.path.getsize(pmo_file)}")
                import traceback
                traceback.print_exc()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('inputfolder')
    parser.add_argument('outputfolder')
    args = parser.parse_args()

    inputfolder = args.inputfolder
    outputfolder = args.outputfolder

    os.makedirs(outputfolder, exist_ok=True)
    batch_pmo(inputfolder, outputfolder)
