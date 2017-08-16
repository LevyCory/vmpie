# ==================================================================================================================== #
# File Name     : plugin.py
# Purpose       : Provide all that you need to write and loan plugins.
# Date Created  : 10/08/2017
# Author        : Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

import os
import re
import sys
import imp
import shutil
from ConfigParser import SafeConfigParser

import consts

# ===================================================== CLASSES ====================================================== #


class Plugin(object):
    """
    Represent a VM plugin.
    In order to write VM plugins you must derive from this class, name your class <Plugin Name>Plugin
    and define its name and compatible operating systems.
    The name must be defined in the inherited attribute I{_name}, and the os must be added to the list I{_os}
    """
    _os = []
    _name = None

    def __init__(self, vm):
        self.vm = vm
    def __str__(self):
        return "<Plugin {name} for {os}>".format(name=self._name, os=str(self._os))

    def __repr__(self):
        return "<Plugin {name} for {os}>".format(name=self._name, os=str(self._os))


class PluginManager(object):
    """
    A plugin manager that provide all sorts of plugin operations.
    Must not be instanced more than once (Singleton).
    """
    def __init__(self):
        self._config = SafeConfigParser()
        self._config.read(consts.PLUGINS_CONFIG_FILE)

        # Append the plugin directory to the $PATH to import plugins easily
        sys.path.append(consts.USER_PLUGIN_FOLDER)

    def _write_config(self):
        """
        Save changes to the configuration file.
        """
        with open(consts.PLUGINS_CONFIG_FILE, "w") as cfg:
            self._config.write(cfg)

    def _get_plugins(self, module, enabled_only=True):
        """
        Get all plugins from module.
        @param module: The module to extract the plugins from.
        @type module: I{module object}
        @param enabled_only: If set to True, will load only enabled plugins.
        @type enabled_only: I{boolean}
        @return: The plugins extracted from the modules.
        @rtype: I{list}
        """
        plugins = []

        for attribute in dir(module):
            # Check if the class name is a valid plugin name
            if re.match(consts.VM_PLUGIN_REGEX, attribute):
                plugin = getattr(module, attribute)

                # Validate plugin
                if self.is_plugin_valid(plugin):
                    # If the 'enabled_only' is set to True, check if the plugin is enabled.
                    if enabled_only:
                        if self.is_plugin_enabled(plugin):
                            plugins.append(plugin)

                    else:
                        plugins.append(plugin)

        return plugins

    def _load_module_by_name(self, file_name):
        """
        Load a module using only it's file's location.
        @param file_name: The module file name.
        @type file_name: I{string}
        @return: The loaded module.
        @rtype: I{module}
        """
        mod = __import__(file_name[:-3], globals(), locals(), [], 0)
        return mod
        # return imp.load_source("plugins." + base_name, file_path)

    def _write_initial_config(self, plugin, module_path):
        """

        @param plugin:
        @return:
        """
        section = self._config.add_section(plugin.__class__.__name__)
        self._config.set(section, consts.PLUGIN_NAME_ATTRIBUTE, plugin._name)
        self._config.set(section, consts.PLUGIN_ENABLED_ATTRIBUTE, True)
        self._config.set(section, consts.PLUGIN_OS_ATTRIBUTE, plugin._os)
        self._config.set(section, consts.PLUGIN_PATH_ATTRIBUTE, module_path)

        self._write_config()

    @property
    def enabled_plugin_names(self):
        """
        Return all enabled plugin names, to use in the vmplugin command line tool.
        @return: All enabled plugin names.
        @rtype: I{list}
        """
        return {plugin["name"] for plugin in self.plugin_data if plugin["enabled"]}

    @property
    def disabled_plugin_names(self):
        """
        Return all disabled plugin names, to use in the vmplugin command line tool.
        @return: All disabled plugin names.
        @rtype: I{list}
        """
        return {plugin["name"] for plugin in self.plugin_data if not plugin["enabled"]}

    @property
    def plugin_data(self):
        """
        Return all plugin data.
        Each plugin is represented by a dictionary with the following values:

            1. I{class} - The name of the class the plugin is defined in.
            2. I{name} - The alias of the plugin.
            3. I{os} - Operating systems compatible with the plugin.
            4. I{enabled} - A boolean indicating whether a plugin is enabled or not.
            5. I{path} - The path to the plugin's file.

        @return: A list with data regarding all plugins.
        @rtype: I{list of dictionaries}
        """
        plugins = []
        
        # Iterate each plugin in the configuration file and create a dictionary with it's data.
        for plugin in self._config.sections():
            plugins.append({
                "class": plugin,
                "name": self._config.get(plugin, consts.PLUGIN_NAME_ATTRIBUTE),
                "os": self._config.get(plugin, consts.PLUGIN_OS_ATTRIBUTE),
                "enabled": eval(self._config.get(plugin, consts.PLUGIN_ENABLED_ATTRIBUTE)),
                "file": self._config.get(plugin, consts.PLUGIN_PATH_ATTRIBUTE)
            })

        return plugins

    def is_plugin_enabled(self, plugin):
        """
        Check whether a plugin is enabled or not.
        @return: Whether a plugin is enabled or not.
        @rtype: I{boolean}
        """
        return eval(self._config.get(plugin.__name__, consts.PLUGIN_ENABLED_ATTRIBUTE))

    def is_plugin_valid(self, plugin):
        """
        Check if a plugin is valid. A plugin is valid if it answers to following conditions:

            1. It is a subclass of Plugin
            2. Its name is not None
            3. It is compatible with at least one OS.

        @param plugin: The plugin to be validated.
        @type plugin: vmpie.Plugin
        @return: Whether a plugin is valid or not.
        @rtype: I{boolean}
        """
        if issubclass(plugin, Plugin):
            return plugin._name is not None and len(plugin._os) > 0
        return False

    def install_plugin(self, module_path):
        """
        Install a plugin.
        Installing a plugin is copying the file it's defined in to the plugin folder, and
        writing it's configuration details to the plugin config file.
        @param module_path: The path of the plugin's module.
        @type: I{string}
        """
        # Copy the file to the plugin directory
        shutil.copy(module_path, consts.USER_PLUGIN_FOLDER)

        # Construct the new file path
        base_name = os.path.basename(module_path)
        new_module_location = os.path.join(consts.USER_PLUGIN_FOLDER, base_name)

        # Load the new module
        module_obj = self._load_module_by_name(new_module_location)

        # Get all plugins from the module
        plugins = self._get_plugins(module_obj, enabled_only=False)

        # For each plugin, write its configuration in the file.
        for plugin in plugins:
            self._write_initial_config(plugin, module_path)

        self._write_config()

    def uninstall_plugin(self, file_name):
        """
        Uninstall a plugin.
        Uninstalling plugins is done by deleting the plugin's file and configuration.
        @param file_name: The name of the file to delete.
        @type file_name: I{string}
        """
        pass

    def collect_plugins(self):
        """
        Load all enabled plugins according the configuration file.
        @return: The collected plugins.
        @rtype: I{list}
        """
        plugins = []

        for plugin in self._config.sections():
            # If the plugin is enabled, load it from it's module and add it to the list
            if eval(self._config.get(plugin, consts.PLUGIN_ENABLED_ATTRIBUTE)):
                file_path = self._config.get(plugin, consts.PLUGIN_PATH_ATTRIBUTE)

                # Load the module
                module_obj = self._load_module_by_name(file_path)

                # Add loaded plugins to the list
                plugins.extend(self._get_plugins(module_obj))

        return list(set(plugins))

    def enable_plugin(self, plugin_name):
        """
        Enable a plugin, which means it'll be loaded to every compatible virtual machine.
        @param plugin_name: The name of the plugin to enable.
        @type plugin_name: I{string}
        """
        # Find the desired plugin
        for plugin in self._config.sections():
            if self._config.get(plugin, consts.PLUGIN_NAME_ATTRIBUTE) == plugin_name:
                # Set the plugin state to 'enabled'
                self._config.set(plugin, consts.PLUGIN_ENABLED_ATTRIBUTE, "True")

        # Save the configuration changes
        self._write_config()

    def disable_plugin(self, plugin_name):
        """
        Disable a plugin, which means it won't be loaded to virtual machines at all.
        @param plugin_name: The name of the plugin to disable.
        @type plugin_name: I{string}
        """
        # Find the desired plugin
        for plugin in self._config.sections():
            if self._config.get(plugin, consts.PLUGIN_NAME_ATTRIBUTE) == plugin_name:
                # Set the plugin state to 'disabled'
                self._config.set(plugin, consts.PLUGIN_ENABLED_ATTRIBUTE, "False")

        # Save the configuration changes
        self._write_config()

