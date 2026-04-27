import os
import struct
import argparse
from convert import load_pmo


def convert_pmo(pmo_file: str):
    load_pmo(pmo_file)


def main():
    parser = argparse.ArgumentParser(description='Converts a Monster Hunter PMO file to Wavefront OBJ format')
    parser.add_argument('pmo_file', help='PMO input file')
    # parser.add_argument('mtl_file', help='MTL input file')
    # parser.add_argument('output_file', help='OBJ output file')
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    # os.makedirs(os.path.dirname(args.output_file), exist_ok=True)
    convert_pmo(args.pmo_file)


if __name__ == '__main__':
    main()
