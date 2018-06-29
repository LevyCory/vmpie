# ==================================================================================================================== #
# File Name     : registry.py
# Purpose       : Provide a convenient way to perform filesystem related operations on virtual machines.
# Date Created  : 29/06/2018
# Author        : Avital Livshits, Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

import vmpie.plugin as plugin

# ==================================================== CONSTANTS ===================================================== #

PLUGIN_NAME = "registry"

# ===================================================== CLASSES ====================================================== #

class WindowsRegistryPlugin(plugin.Plugin):
    """

    """
    _os = [plugin.WINDOWS]
    _name = PLUGIN_NAME

    def get_value(self):
        """

        @return:
        """
        raise NotImplementedError()

    def set_value(self):
        """

        @return:
        """
        raise NotImplementedError()
