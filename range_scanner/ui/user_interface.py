# context.area: VIEW_3D

import importlib
import os
import pathlib
import random
import subprocess
import sys
import time
from math import radians

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Operator, Panel, PropertyGroup, UIList
from bpy.utils import unregister_class
from mathutils import Euler, Vector

from ..scanners import generic

# add-on skeleton taken from: https://blender.stackexchange.com/a/57332

# metainfo https://wiki.blender.org/wiki/Process/Addons/Guidelines/metainfo
bl_info = {
    "name": "range_scanner", # name of the add-on
    "description": "Range scanner simulation for Blender", # used for the tooltip and addons list
    "author": "Lorenzo Neumann", # author of the add-on
    "blender": (3, 4, 0), # blender version
    "version": (0, 1, 0), # major, minor, patch
    "location": "View3D > Scanner", # where to find it in the UI
    "doc_url": "https://git.informatik.tu-freiberg.de/masterarbeit/blender-range-scanner", # documentation URL
    "warning": "", # used for warning icon and text in addons panel
    "category": "3D View", # category in the addons panel
    "support": "COMMUNITY",
}


class MAIN_PANEL:
    """Main panel for the range scanner add-on
    defines the location of the panel in the UI
    in this case it is located as a tab in the 3D Viewport
    """

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Scanner"




#############################################################
#                                                           #
#                   WATER PROFILE LIST                      #
#                                                           #
#############################################################


def sortList(customList):
    # sort list items
    # selection sort is just fine as it is simple and we don't have that many items
    # see: https://en.wikipedia.org/wiki/Selection_sort#Implementations
    for index in range(len(customList.items()) - 1):
        minimumIndex = index

        for innerIndex in range(index, len(customList.items())):
            if customList.items()[innerIndex][1].depth < customList.items()[minimumIndex][1].depth:
                minimumIndex = innerIndex

        customList.move(minimumIndex, index)


# adapted from https://blender.stackexchange.com/a/30446/95167
def addItemToList(scene, depth, speed, density, customList):
    # add new item to the list
    item = customList.add()
    item.name = str(depth)
    item.depth = depth
    item.speed = speed
    item.density = density
    scene.custom_index = len(customList) - 1


def removeDuplicatesFromList(scene, customList):
    # remove potential duplicates
    removed_items = []
    for i in find_duplicates(customList)[::-1]:
        customList.remove(i)
        removed_items.append(i)

    if removed_items:
        scene.custom_index = len(customList) - 1


def find_duplicates(customList):
    """find all duplicates by name"""
    name_lookup = {}
    for c, i in enumerate(customList):
        name_lookup.setdefault(i.depth, []).append(c)
    duplicates = set()
    for _name, indices in name_lookup.items():
        for i in indices[:-1]:
            duplicates.add(i)
    return sorted(duplicates)


class CUSTOM_OT_addItem(Operator):
    """Add item"""

    bl_idname = "custom.add_items"
    bl_label = "Add /Edit item"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        scene = context.scene

        addItemToList(
            scene,
            scene.scannerProperties.refractionDepth,
            scene.scannerProperties.refractionSpeed,
            scene.scannerProperties.refractionDensity,
            scene.custom,
        )

        removeDuplicatesFromList(scene, scene.custom)

        sortList(scene.custom)

        return {"FINISHED"}


class CUSTOM_OT_removeItem(Operator):
    """Remove item"""

    bl_idname = "custom.remove_item"
    bl_label = "Remove item"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        scn = context.scene

        # source: https://sinestesia.co/blog/tutorials/using-uilists-in-blender/
        index = scn.custom_index
        my_list = scn.custom

        my_list.remove(index)
        scn.custom_index = min(max(0, index - 1), len(my_list) - 1)

        return {"FINISHED"}


class CUSTOM_OT_clearList(Operator):
    """Clear all items of the list"""

    bl_idname = "custom.clear_list"
    bl_label = "Clear List"
    bl_description = "Clear all items of the list"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.custom)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        if bool(context.scene.custom):
            context.scene.custom.clear()
            self.report({"INFO"}, "All items removed")
        else:
            self.report({"INFO"}, "Nothing to remove")
        return {"FINISHED"}


class CUSTOM_UL_items(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if index == len(context.scene.custom) - 1:
            layout.label(
                text="Depth: > %.2f m, Speed: %.3f m/s, Density: %.3f kg/m³" % (item.depth, item.speed, item.density)
            )
        else:
            layout.label(
                text="Depth: %.2f m - %.2fm, Speed: %.3f m/s, Density: %.3f kg/m³"
                % (item.depth, context.scene.custom[index + 1].depth, item.speed, item.density)
            )

    def invoke(self, context, event):
        pass


class CUSTOM_objectCollection(PropertyGroup):
    depth: FloatProperty()
    speed: FloatProperty()
    density: FloatProperty()


# merge all classes to be displayed
classes = (
    WM_OT_INSTALL_DEPENDENCIES,
    WM_OT_LOAD_PRESET,
    EXAMPLE_PT_DEPENDENCIES_PANEL,
    ScannerProperties,
    WM_OT_GENERATE_POINT_CLOUDS,
    OBJECT_PT_MAIN_PANEL,
    OBJECT_PT_PRESET_PANEL,
    OBJECT_PT_SCANNER_PANEL,
    OBJECT_PT_REFLECTIVITY_PANEL,
    OBJECT_PT_ANIMATION_PANEL,
    OBJECT_PT_OBJECT_MODIFICATION_PANEL,
    OBJECT_PT_NOISE_PANEL,
    OBJECT_PT_WEATHER_PANEL,
    OBJECT_PT_VISUALIZATION_PANEL,
    OBJECT_PT_EXPORT_PANEL,
    OBJECT_PT_DEBUG_PANEL,
    CUSTOM_OT_addItem,
    CUSTOM_OT_removeItem,
    CUSTOM_OT_clearList,
    CUSTOM_UL_items,
    CUSTOM_objectCollection,
)

config = []


# register all needed classes on startup
def register():
    global config

    global dependencies_installed
    dependencies_installed = False

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.scannerProperties = PointerProperty(type=ScannerProperties)
    bpy.types.Scene.custom = CollectionProperty(type=CUSTOM_objectCollection)
    bpy.types.Scene.custom_index = IntProperty()

    missingDependency = None

    try:
        requirementsPath = os.path.join(pathlib.Path(__file__).parent.parent.absolute(), "requirements.txt")
        print("Reading dependencies from {0}".format(requirementsPath))
        requirementsFile = open(requirementsPath, "r")
        requirements = requirementsFile.readlines()

        importName = None

        # Strips the newline character
        for requirement in requirements:
            stripped = requirement.strip()

            if stripped.startswith("#/"):
                importName = stripped.split("#/")[1]
                continue

            if stripped.startswith("#") or not stripped:
                continue

            name, version = stripped.split("==")

            if importName is None:
                importName = name

            print(f"Checking {name}: version {version}, import {importName}")

            missingDependency = name
            import_module(module_name=importName)

            importName = None

        dependencies_installed = True
        missingDependency = None

        print("All dependencies found.")
    except ModuleNotFoundError:
        print("ERROR: Missing dependency %s." % str(missingDependency))
        # Don't register other panels, operators etc.
        return

    # load scanner config file
    configPath = os.path.join(pathlib.Path(__file__).parent.absolute(), "presets.yaml")

    print("Loading config file from %s ..." % configPath)

    with open(configPath, "r") as stream:
        try:
            # we can't load it before checking for our dependencies, as we need the yaml module here
            import yaml

            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    print("Done.")


# delete all classes on shutdown
def unregister():
    for cls in reversed(classes):
        unregister_class(cls)

    del bpy.types.Scene.scannerProperties
    del bpy.types.Scene.custom
    del bpy.types.Scene.custom_index
