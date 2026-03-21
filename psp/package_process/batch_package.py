import os
import array
import argparse
from pathlib import Path

def extract_top_dir(folder_path, new_save_path):
    folder = Path(folder_path)
    pac_files = list(folder.glob("*.pac"))
    for f in pac_files:
        basename = os.path.basename(f)
        save_file_path = os.path.join(new_save_path, basename)
        with open(f, 'rb') as package:
            file_count = array.array('I', package.read(4))[0]
            file_info = array.array('I', package.read(file_count * 8))
            for i in range(file_count):
                offset = file_info[i * 2]
                size = file_info[i * 2 + 1]
                package.seek(offset)
                data = package.read(size)
                base, ext = os.path.splitext(save_file_path)
                out_path = f"{base}-{i:04d}{ext}"
                with open(out_path, 'wb') as f:
                    f.write(data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('inputfolder')
    parser.add_argument('outputfolder')
    args = parser.parse_args()

    inputfolder = args.inputfolder
    outputfolder = args.outputfolder

    os.makedirs(outputfolder, exist_ok=True)
    extract_top_dir(inputfolder, outputfolder)
