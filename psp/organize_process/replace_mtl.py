import os
import re
import argparse

def place_mtl_in_obj(obj_file, mtl_name):
    if os.path.exists(obj_file):
        with open(obj_file, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        text = re.sub(r"^mtllib\s+.*$", f"mtllib {mtl_name}", text, flags=re.MULTILINE)
        with open(obj_file, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Replaced obj's mtl path to {mtl_name}")
    else:
        print(f"Path DNE: {obj_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('obj_file')
    parser.add_argument('mtl_name')
    args = parser.parse_args()
    place_mtl_in_obj(args.obj_file, args.mtl_name)
