import os
import re
import imp
import shutil
from ConfigParser import SafeConfigParser

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

    def __init__(self, vm):
        self.vm = vm

    def __str__(self):
        return "<Plugin {name} for {os}>".format(name=self._name, os=str(self._os))

    def __repr__(self):
        return "<Plugin {name} for {os}>".format(name=self._name, os=str(self._os))


class PluginManager(object):
    """

    """
    def __init__(self):
        self.config = SafeConfigParser().read("")

    def _write_config(self):
        """

        @return:
        """
        with open(consts.PLUGINS_CONFIG_FILE, "w") as cfg:
            self.config.write(cfg)

    def _get_plugins(self, module):
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
                if self.is_plugin_valid(plugin) and self.is_plugin_enabled(plugin):
                    plugins.append(plugin)

        return plugins

    @property
    def enabled_plugins(self):
        """

        @return:
        """
        enabled_plugins = []
        for plugin in self.config.sections():
            if self.config.get(plugin, consts.PLUGIN_ENABLED_ATTRIBUTE):
                enabled_plugins.append(plugin)

        return enabled_plugins

    @property
    def plugins(self):
        """

        @return:
        """
        return {self.config.get(section, consts.PLUGIN_NAME_ATTRIBUTE) for section in self.config.sections()}

    def is_plugin_enabled(self, plugin):
        """

        @return:
        """
        return eval(self.config.get(plugin.__class__.__name__, consts.PLUGIN_ENABLED_ATTRIBUTE))

    def is_plugin_valid(self, plugin):
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

    def install_plugin(self, module_path):
        """

        @param module_path:
        @return:
        """
        shutil.copy(module_path, "")
        plugins = self._get_plugins(module_path)
        for plugin in plugins:
            self.config.add_section(plugin.__class__.__name__)
            self.config.set(plugin._name, consts.PLUGIN_ENABLED_ATTRIBUTE, True)
            self.config.set(plugin._name, consts.PLUGIN_PATH_ATTRIBUTE, module_path)
            self.config.set(plugin._name, consts.PLUGIN_NAME_ATTRIBUTE, plugin._name)
            self.config.set(plugin._name, consts.PLUGIN_OS_ATTRIBUTE, plugin._os)
        self._write_config()

    def uninstall_plugin(self, module_path):
        """

        @param module_path:
        @return:
        """
        pass

    def _collect_plugins(self):
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

        for section in self.config.sections():
            if self.config.get(section, consts.PLUGIN_ENABLED_ATTRIBUTE) == "True":
                file_path = self.config.get(section, consts.PLUGIN_PATH_ATTRIBUTE)
                base_name = os.path.basename(file_path)
                mod = imp.load_source(base_name, file_path)
                plugins.extend(self._get_plugins(mod))

        return plugins

    def enable_plugin(self, plugin_name):
        """
        @param plugin_name:
        @return:
        """
        for plugin in self.config.sections:
            if self.config.get(plugin, consts.PLUGIN_NAME_ATTRIBUTE) == plugin_name:
                self.config.set(plugin, consts.PLUGIN_ENABLED_ATTRIBUTE, False)

        self._write_config()

    def disable_plugin(self, plugin_name):
        """

        @param plugin_name:
        @return:
        """
        for plugin in self.config.sections:
            if self.config.get(plugin, consts.PLUGIN_NAME_ATTRIBUTE) == plugin_name:
                self.config.set(plugin, consts.PLUGIN_ENABLED_ATTRIBUTE, False)

        self._write_config()

