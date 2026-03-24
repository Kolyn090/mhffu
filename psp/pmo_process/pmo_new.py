#!/usr/bin/python3

# Copyright 2013 Seth VanHeulen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import os
import struct
from convert import convert_mh2_pmo, convert_mh3_pmo

def convert_pmo(pmo_file, mtl_file, 
                obj_file, second_file=None, 
                verbose=False, enforce_ge_verbose=False):
    mtl_file = os.path.basename(mtl_file)
    second = None
    if second_file:
        second = open(second_file, 'rb')
    with open(pmo_file, 'rb') as pmo:
        type, version = struct.unpack('4s4s', pmo.read(8))
        if type == b'pmo\x00' and version == b'102\x00':
            with open(obj_file, 'w') as obj:
                obj.write('mtllib {}\n'.format(mtl_file))
                convert_mh3_pmo(pmo, obj, second)
        elif type == b'pmo\x00' and version == b'1.0\x00':
            dirname = os.path.dirname(obj_file)
            basename = os.path.basename(obj_file)
            convert_mh2_pmo(pmo, mtl_file, dirname, basename, second, verbose, enforce_ge_verbose)
        else:
            if second:
                second.close()
            raise ValueError('Invalid PMO file')
    if second:
        second.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Converts a Monster Hunter PMO file to Wavefront OBJ format')
    parser.add_argument('pmofile', help='PMO input file')
    parser.add_argument('mtlfile', help='MTL input file')
    parser.add_argument('outputfile', help='OBJ output file')
    parser.add_argument('--second', help='Second part of large monster PMO', required=False)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--enforce_ge_verbose", action="store_true")
    args = parser.parse_args()
    outputfile = args.outputfile
    os.makedirs(os.path.dirname(outputfile), exist_ok=True)
    convert_pmo(args.pmofile, args.mtlfile, outputfile, args.second, args.verbose, args.enforce_ge_verbose)
