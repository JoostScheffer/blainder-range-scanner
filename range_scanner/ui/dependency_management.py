from __future__ import annotations

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
from .base_classes import MAIN_PANEL

#############################################################
#                                                           #
#                 DEPENDENCY MANAGEMENT                     #
#                                                           #
#############################################################


# source: https://github.com/robertguetzkow/blender-python-examples/tree/master/add-ons/install-dependencies

#    Copyright (C) 2020  Robert Guetzkow
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>


dependencies_installed = False


# def import_module(module_name, global_name=None):
# make global_name an optional parameter
def import_module(module_name: str, global_name: str | None = None):
    r"""Import a module.

    Parameters
    ----------
    module_name : str
        Module to import.
    global_name : str, optional
        Name under which the module is imported. If None the module_name will be used.
        This allows to import under a different name with the same effect as e.g. "import numpy as np" where "np" is
        the global_name under which the module can be accessed.

    Raises
    ------
    ImportError
        If the module can't be imported.
    ModuleNotFoundError
        If the module can't be found.
    """

    if global_name is None:
        global_name = module_name

    # Attempt to import the module and assign it to globals dictionary. This allow to access the module under
    # the given name, just like the regular import would.
    globals()[global_name] = importlib.import_module(module_name)


def install_pip():
    r"""Installs pip if not already present.

    Raises
    ------
    subprocess.CalledProcessError
        If the installation fails.

    Notes
    -----
    Please note that `ensurepip.bootstrap()` also calls pip, which adds the
    environment variable PIP_REQ_TRACKER. After ensurepip.bootstrap() finishes execution, the directory doesn't exist
    anymore. However, when subprocess is used to call pip, in order to install a package, the environment variables
    still contain PIP_REQ_TRACKER with the now nonexistent path. This is a problem since pip checks if PIP_REQ_TRACKER
    is set and if it is, attempts to use it as temp directory. This would result in an error because the
    directory can't be found. Therefore, PIP_REQ_TRACKER needs to be removed from environment variables.

    """
    try:
        # Check if pip is already installed
        subprocess.run([sys.executable, "-m", "pip", "--version"], check=True)
    except subprocess.CalledProcessError:
        import ensurepip

        ensurepip.bootstrap()
        os.environ.pop("PIP_REQ_TRACKER", None)


def install_and_import_module(module: str, importName: str):
    r"""Installs the package through pip and attempts to import the installed module.

    Parameters
    ----------
    module : str
        Module to import.
    importName : str
        Name under which the module is imported. If None the module_name will be used.
        This allows to import under a different name with the same effect as e.g. "import numpy as np" where "np" is
        the global_name under which the module can be accessed.

    Raises
    ------
    subprocess.CalledProcessError
        If the installation fails.
    ImportError
        If the module can't be imported.

    Notes
    -----
    Blender disables the loading of user site-packages by default. However, pip will still check them to determine
    if a dependency is already installed. This can cause problems if the packages is installed in the user
    site-packages and pip deems the requirement satisfied, but Blender cannot import the package from the user
    site-packages. Hence, the environment variable PYTHONNOUSERSITE is set to disallow pip from checking the user
    site-packages. If the package is not already installed for Blender's Python interpreter, it will then try to.
    The paths used by pip can be checked with `subprocess.run([sys.executable, "-m", "site"], check=True)`
    """

    # Store the original environment variables
    environ_orig = dict(os.environ)

    # Disable the user site-packages
    # This is necessary because pip will still check the user site-packages to determine if a package is already
    # installed. However, Blender can't import from the user site-packages, so pip may deem a requirement satisfied
    # even though Blender can't import it.
    os.environ["PYTHONNOUSERSITE"] = "1"

    try:
        print(f"Installing {module}")

        # Try to install the package. This may fail with subprocess.CalledProcessError
        subprocess.run([sys.executable, "-m", "pip", "install", module], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {module}")
        print(e)
    finally:
        # Always restore the original environment variables
        os.environ.clear()
        os.environ.update(environ_orig)

    # The installation succeeded, attempt to import the module again
    import_module(importName)


def parse_requirements_file(filename: str) -> list[tuple[str, str]]:
    """Parses a requirements file and returns a list of tuples containing the package name and version.

    Parameters
    ----------
    filename : str
        Path to the requirements file.

    Returns
    -------
    list[tuple[str,str]]
        List of tuples containing the package name and version.

    Raises
    ------
    FileNotFoundError
        If the file can't be found.
    """

    with open(filename, "r") as requirementsFile:
        requirements = requirementsFile.readlines()

    importName = None
    parsedRequirements = []

    # Strips the newline character
    for requirement in requirements:
        stripped = requirement.strip()

        if stripped.startswith("#/"):
            importName = stripped.split("#/")[1]
            continue

        if stripped.startswith("#") or not stripped:
            continue

        parsedRequirements.append((stripped, importName))

    return parsedRequirements


class WM_OT_INSTALL_DEPENDENCIES(Operator):
    r"""Installs the dependencies for this add-on.

    Notes
    -----
    This operator is only available when the dependencies have not been installed yet.
    """

    bl_label = "Install dependencies"
    bl_idname = "wm.install_dependencies"

    @classmethod
    def poll(cls, context):
        # Deactivate when dependencies have been installed
        return not dependencies_installed

    def execute(self, context) -> set[str] | None:
        try:
            # Install pip if not already present
            install_pip()

            requirementsPath = os.path.join(pathlib.Path(__file__).parent.parent.absolute(), "requirements.txt")
            print(f"Reading dependencies from {requirementsPath}")
            with open(requirementsPath, "r") as requirementsFile:
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

                install_and_import_module(module=stripped, importName=importName)

                importName = None
        except (subprocess.CalledProcessError, ImportError) as err:
            print("ERROR: %s" % str(err))
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}

        global dependencies_installed
        dependencies_installed = True

        return {"FINISHED"}


class EXAMPLE_PT_DEPENDENCIES_PANEL(MAIN_PANEL, Panel):
    r"""Panel to display a message if dependencies are missing.
    """

    bl_label = "Missing dependencies"

    @classmethod
    def poll(cls, context):
        return not dependencies_installed

    def draw(self, context):
        layout = self.layout

        lines = [
            "You need to install some dependencies to use this add-on.",
            "Click the button below to start (requires to run blender",
            "with administrative privileges on Windows).",
        ]
        for line in lines:
            layout.label(text=line)

        # Add button to install dependencies
        # This will call the execute method of the WM_OT_INSTALL_DEPENDENCIES operator
        layout.operator("wm.install_dependencies")
