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
WINREG_TYPE_PREFIX = "REG"

# ===================================================== CLASSES ====================================================== #


class WindowsRegistryPlugin(plugin.Plugin):
    """
    An interface for registry operations
    """
    _os = [plugin.WINDOWS]
    _name = PLUGIN_NAME

    def _setup_(self):
        """
        Load remote VM's constants of base registry keys
        """
        self._base_keys = {
            "HKCR": self.vm.remote._winreg.HKEY_CLASSES_ROOT,
            "HKLM": self.vm.remote._winreg.HKEY_LOCAL_MACHINE,
            "HKCC": self.vm.remote._winreg.HKEY_CURRENT_CONFIG,
            "HKDD": self.vm.remote._winreg.HKEY_DYN_DATA,
            "HKPD": self.vm.remote._winreg.HKEY_PERFORMANCE_DATA,
            "HKCU": self.vm.remote._winreg.HKEY_CLASSES_ROOT,
            "HKU": self.vm.remote._winreg.HKEY_USERS,
        }

        # Inject type constants to the plugin
        for attr in dir(self.vm.remote._winreg):
            if attr.startswith(WINREG_TYPE_PREFIX):
                setattr(self, attr, getattr(self.vm.remote._winreg, attr))

    def _get_base_key(self, base_key):
        """

        @param base_key:
        @return:
        """
        try:
            return self._base_keys[base_key.upper()]
        except ValueError:
            raise

    def get_value(self, base_key, sub_key, name):
        """

        @param base_key:
        @param sub_key:
        @param name:
        @return:
        """
        with self.vm.remote._winreg.OpenKey(self._get_base_key(base_key), sub_key) as reg_key:
            return self.vm.remote._winreg.QueryValueEx(reg_key, name)

    def set_value(self, base_key, sub_key, name, type, value):
        """

        @param base_key:
        @param sub_key:
        @param name:
        @param type:
        @param value:
        @return:
        """
        permissions = self.vm.remote._winreg.KEY_WRITE
        with self.vm.remote._winreg.OpenKey(self._get_base_key(base_key), sub_key, 0, permissions) as reg_key:
            self.vm.remote._winreg.SetValue(reg_key, name, 0, type, value)

    def enumerate_key(self, base_key, sub_key):
        """

        @param base_key:
        @param sub_key:
        @return:
        @rtype: tuple
        """
        index = -1
        permissions = self.vm.remote._winreg.KEY_ENUMERATE_SUB_KEYS
        key = self.vm.remote._winreg.OpenKey(self._get_base_key(base_key), sub_key, 0, permissions)

        # Iterate through registry values
        while True:
            try:
                index += 1
                yield self.vm.remote._winreg.EnumKey(key, index)
            except WindowsError:
                yield StopIteration
            finally:
                key.close()

    def delete_key(self, base_key, sub_key, name):
        """
        Delete a registry key.
        @param base_key:
        @param sub_key:
        @param name:
        @return:
        """
        permissions = self.vm.remote._winreg.KEY_WRITE
        with self.vm.remote._winreg.OpenKey(self._get_base_key(base_key), sub_key, 0, permissions) as reg_key:
            self.vm.remote._winreg.DeleteKeyEx(reg_key, name)
