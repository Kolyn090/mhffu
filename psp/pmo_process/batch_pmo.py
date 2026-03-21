import os
import argparse
from pmo_new import convert_pmo
from pathlib import Path

debug = False

def is_valid_pmo(path):
    with open(path, 'rb') as f:
        header = f.read(8)
        return header.startswith(b'pmo\x00')

def batch_pmo(folder_path, new_save_path, pmo1_code, pmo2_code, mtl1_code, mtl2_code):
    folder = Path(folder_path)
    pac_files = list(folder.glob("*.pac"))
    pmo_files1 = []
    pmo_files2 = []
    mtl_files1 = []
    mtl_files2 = []

    for f in pac_files:
        basename = os.path.basename(f)
        if pmo1_code and pmo1_code in basename:
            pmo_files1.append(f)
        if pmo2_code and pmo2_code in basename:
            pmo_files2.append(f)
        if mtl1_code and mtl1_code in basename:
            mtl_files1.append(f)
        if mtl2_code and mtl2_code in basename:
            mtl_files2.append(f)

    for pmo_file, mtl_file in zip(pmo_files1, mtl_files1):
        if not is_valid_pmo(pmo_file):
            print(f"Skipping non-PMO: {pmo_file}")
            continue
        basename = os.path.basename(pmo_file).replace(f"-{pmo1_code}.pac", f"-{pmo1_code}.obj")
        save_file_path = os.path.join(new_save_path, basename)
        try:
            convert_pmo(pmo_file, mtl_file, save_file_path)
        except Exception as e:
            print(f"Failed to process {pmo_file}")
            if debug:
                print(f"File size: {os.path.getsize(pmo_file)}")
                import traceback
                traceback.print_exc()

    for pmo_file, mtl_file in zip(pmo_files2, mtl_files2):
        if not is_valid_pmo(pmo_file):
            print(f"Skipping non-PMO: {pmo_file}")
            continue
        basename = os.path.basename(pmo_file).replace(f"-{pmo2_code}.pac", f"-{pmo2_code}.obj")
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
    parser.add_argument('--pmo1_code', required=True)
    parser.add_argument('--mtl1_code', required=True)
    parser.add_argument('--pmo2_code', required=False)
    parser.add_argument('--mtl2_code', required=False)
    args = parser.parse_args()

    inputfolder = args.inputfolder
    outputfolder = args.outputfolder
    pmo1_code = args.pmo1_code
    mtl1_code = args.mtl1_code
    pmo2_code = args.pmo2_code
    mtl2_code = args.mtl2_code

    os.makedirs(outputfolder, exist_ok=True)
    batch_pmo(inputfolder, outputfolder, pmo1_code, pmo2_code, mtl1_code, mtl2_code)
