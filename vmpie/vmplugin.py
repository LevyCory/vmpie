# ==================================================================================================================== #
# File Name     : vmplugin.py
# Purpose       : Allow users to install, remove, enable or disable plugins.
# Date Created  : 10/08/2017
# Author        : Cory Levy
# ==================================================================================================================== #
# ==================================================== CHANGELOG ===================================================== #
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

import os
import shutil
import argparse

import vmpie

# ==================================================== CONSTANTS ===================================================== #
# ===================================================== GLOBALS ====================================================== #
# ===================================================== CLASSES ====================================================== #
# ==================================================== FUNCTIONS ===================================================== #


def get_args():
    """
    """
    parser = argparse.ArgumentParser("The VM-Plugin manager")
    parser.add_argument("list", action="store_true", type=bool, help="List all installed VM-Plugins")
    parser.add_argument("install", action="store", type=str, help="Install new VM-Plugin")
    parser.add_argument("remove", action="store", type=str, help="Remove an existing VM-Plugin")
    parser.add_argument("enable", action="store", type=str, help="Enable VM-Plugin")
    parser.add_argument("disable", action="store", type=str, help="Disable VM-Plugin")

    return parser.parse_args()


def main():
    """
    """
    args = get_args()

    if args.list:
        # Print all plugin names
        for plugin in vmpie._plugins:
            print plugin._name

    elif args.install:
        # Copy the plugin file to vmpie's plugin folder
        shutil.copy2(args.add, USER_PLUGIN_FOLDER)

    elif args.remove:
        # Delete the file
        try:
            os.remove(args.remove)
        except OSError:
            print "ERROR: Plugin {name} is not installed.".format(name=args.remove)

    elif args.enable:
        pass

    elif args.disable:
        pass
