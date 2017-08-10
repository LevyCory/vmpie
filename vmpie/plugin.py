import os
import re

import consts


class Plugin(object):
    """
    Represent a VM plugin.
    In order to write VM plugins you must derive from this class, name your class <Plugin Name>Plugin
    and define its name and compatible operating systems.
    The name must be defined in the inherited attribute I{_name), and the os must be added to the list I{_os)
    """
    _os = []
    _name = None
    _is_enabled = True

    def __init__(self, vm):
        self.vm = vm

    def __str__(self):
        return "<Plugin {name} for {os}>".format(name=self._name, os=str(self._os))

    def __repr__(self):
        return "<Plugin {name} for {os}>".format(name=self._name, os=str(self._os))


def _is_plugin_valid(plugin):
    """
    Check if a plugin is valid. A plugin is valid if it answers to following conditions:
    1. It is a subclass of Plugin
    2. Its name is not None
    3. It is compatible with at least one OS.
    @param plugin: The plugin to be validated.
    @type plugin: vmpie.Plugin
    @return: Whether a plugin is valid or not.
    @rtype: I{Boolean}
    """
    if isinstance(plugin, Plugin):
        return plugin._name is not None and len(plugin._os) > 0
    return False


def _get_plugins(module):
    """
    Get all plugins from module.
    @param module: The module to extract the plugins from.
    @type module: I{module object}
    @return: The plugins extracted from the modules.
    @rtype: I{list}
    """
    plugins = []

    for attribute in dir(module):
        # Check if the class name is a valid plugin name
        if re.match(consts.VM_PLUGIN_REGEX, attribute):
            plugin = getattr(module, attribute)

            # Validate plugin
            if _is_plugin_valid(plugin):
                plugins.append(plugin)

    return plugins


def _collect_plugins(directories, recursive=True):
    """
    Collect all plugins from the given directories.
    @param directories: The directories to collect the plugins from.
    @type directories: I{list}
    @param recursive: Whether to search plugin recursively or not.
    @type recursive: I{boolean}
    @return: The collected plugins.
    @rtype: I{list}
    """
    plugins = []

    #TODO: Implement recursive option
    for directory in directories:
        # Traverse the directory tree recursively
        for _, _, child in os.walk(directory):
            # Ensure only python files will be loaded
            if re.match(consts.PYTHON_FILE_REGEX, child):
                module = __import__(child[-3:])

                # Extract the plugins from the module
                plugins.extend(_get_plugins(module))

    return plugins
