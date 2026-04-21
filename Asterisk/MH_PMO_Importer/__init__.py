# -*- coding: utf-8 -*-
"""
Created on Wed Mar  6 13:38:47 2019

@author: AsteriskAmpersand
"""
#from .dbg import dbg_init
#dbg_init()

content=bytes("","UTF-8")
bl_info = {
    "name": "MH PMO Model Importer",
    "category": "Import-Export",
    "author": "AsteriskAmpersand (Code) & Seth VanHeulen (Vertex and Face Buffer Structure)",
    "location": "File > Import-Export > PMO/MH",
    "version": (1,0,0)
}
 
import bpy

from .operators.importer import menu_func_import as pmo_model_menu_func_import
from .operators.importer import ImportPMO,ImportCMO
from .operators.ahi_import import ImportFUAHI
from .operators.ahi_import import menu_func_import as ahi_skeleton_menu_func_import
from .operators.ahi_converter import ConvertAHI

classes = [ImportPMO,ImportCMO,ImportFUAHI,ConvertAHI]

def register():
    print("REGISTERING ADDON")

    # Force clean state
    for cl in classes:
        try:
            bpy.utils.unregister_class(cl)
        except:
            pass

    for cl in classes:
        print("Register:", cl)
        bpy.utils.register_class(cl)

    try:
        bpy.types.TOPBAR_MT_file_import.remove(pmo_model_menu_func_import)
    except:
        pass

    try:
        bpy.types.TOPBAR_MT_file_import.remove(ahi_skeleton_menu_func_import)
    except:
        pass

    bpy.types.TOPBAR_MT_file_import.append(pmo_model_menu_func_import)
    bpy.types.TOPBAR_MT_file_import.append(ahi_skeleton_menu_func_import)

    print("REGISTER OK")

def unregister():
    for cl in reversed(classes):
        try:
            bpy.utils.unregister_class(cl)
        except:
            pass

    try:
        bpy.types.TOPBAR_MT_file_import.remove(pmo_model_menu_func_import)
        bpy.types.TOPBAR_MT_file_import.remove(ahi_skeleton_menu_func_import)
    except:
        pass

if __name__ == "__main__":
    try:
        unregister()
    except:
        pass
    register()
