# ==================================================================================================================== #
# File Name     : vmplugin.py
# Purpose       : Allow users to install, remove, enable or disable plugins.
# Date Created  : 10/08/2017
# Author        : Cory Levy
# ==================================================================================================================== #
# ==================================================== CHANGELOG ===================================================== #
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

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
    parser.add_argument("uninstall", action="store", type=str, help="Remove an existing VM-Plugin")
    parser.add_argument("enable", action="store", type=str, help="Enable VM-Plugin")
    parser.add_argument("disable", action="store", type=str, help="Disable VM-Plugin")

    return parser.parse_args()


def main():
    """
    """
    args = get_args()

    if args.list:
        # Print all plugin names and their compatible operating systems
        for plugin in vmpie._plugin_manager.plugins:
            print plugin["name"]

    elif args.install:
        # Copy the plugin file to vmpie's plugin folder
        vmpie._plugin_manager.install_plugin(args.install)

    elif args.uninstall:
        # Delete the file
        try:
            vmpie._plugin_manager.install_plugin(args.uninstall)
        except OSError:
            print "ERROR: Plugin {name} is not installed.".format(name=args.remove)

    elif args.enable:
        vmpie._plugin_manager.enable_plugin(args.enable)

    elif args.disable:
        vmpie._plugin_manager.disable_plugin(args.disable)
