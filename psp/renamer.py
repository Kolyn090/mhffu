import csv
import glob
import hashlib
import json
import os
import shutil
import sys
from io import BytesIO
from pathlib import Path

def get_filelist(filename):
    nfilelist = {}
    with open(filename) as f:
        reader = csv.reader(f)
        for idx, path in reader:
            fname = Path(path).name
            nfilelist.setdefault(fname, [idx, path])    # 0 = ID, 1 = full path

    return nfilelist

def rename_dump_files(outfolder):
    allfiles = glob.glob(f"{outfolder}/*", recursive=True)
    inv_filelist = dict((v[0], v[1]) for k, v in filelist.items())

    for f in allfiles:
        npath = inv_filelist[Path(f).name]
        new_folders = Path(outfolder).joinpath(Path(npath).parent)
        os.makedirs(new_folders, exist_ok=True)

        dest = Path(outfolder).joinpath(npath)
        shutil.move(f, dest)

filelist = get_filelist("filelist.csv")
rename_dump_files("out")
