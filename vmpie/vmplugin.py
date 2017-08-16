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

PLUGIN_PRINT_FORMAT = "{path} -> {plugin_name}"

# ===================================================== GLOBALS ====================================================== #
# ===================================================== CLASSES ====================================================== #
# ==================================================== FUNCTIONS ===================================================== #


def get_arg_parser():
    """
    Return an argument parser object for processing command line arguments.
    @return: Argument parser.
    @rtype: I{argparse.ArgumentParser}
    """
    parser = argparse.ArgumentParser("The VM-Plugin manager")

    parser.add_argument("-i", "--install", help="Install new VM-Plugin")
    parser.add_argument("-u", "--uninstall", help="Remove an existing VM-Plugin")
    parser.add_argument("-e", "--enable", help="Enable VM-Plugin")
    parser.add_argument("-d", "--disable", help="Disable VM-Plugin")
    parser.add_argument("-l", "--list", action="store_true", help="List all installed VM-Plugins")

    return parser


def main():
    arg_parser = get_arg_parser()
    args = arg_parser.parse_args()

    if args.list:
        # Print all plugin names and their compatible operating systems
        for plugin in vmpie._plugin_manager.plugin_data:
            print PLUGIN_PRINT_FORMAT.format(plugin_name=plugin["name"], path=plugin["file"])

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

    else:
        arg_parser.print_help()


if __name__ == '__main__':
    main()
