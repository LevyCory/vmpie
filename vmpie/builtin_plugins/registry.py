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
        Load remote VM's constants of base registry keys and permission related constants
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
        Return the corresponding constant for a given registry base key.
        @param base_key: The base key.
        @type base_key: I{str}
        @return: The constant representing the desired base key.
        @rtype: I{int}
        """
        try:
            return self._base_keys[base_key.upper()]
        except ValueError:
            raise ValueError("There is no base key with the name {name}".format(name=base_key))

    def get_value(self, base_key, sub_key, name):
        """
        Read a value with the name I{name} from the registry key I{base_key\sub_key}
        @param base_key: The value's base key.
        @type base_key: I{str}
        @param sub_key: The full path to the value without the base key
        @type sub_key: I{str}
        @param name: The value's name
        @type name: I{str}
        @return: The registry value.
        @rtype: tuple
        """
        with self.vm.remote._winreg.OpenKey(self._get_base_key(base_key), sub_key) as reg_key:
            return self.vm.remote._winreg.QueryValueEx(reg_key, name)

    def set_value(self, base_key, sub_key, name, type, value):
        """
        Set a value on the remote VM's registry.
        @param base_key: The base key of the registry value.
        @type base_key: I{str}
        @param sub_key: The path of the registry key, without the base key.
        @type sub_key: I{str}
        @param name: The name of the value to set.
        @type name: I{str}
        @param type: The data type of the value to set. one of the predefined constants starting with REG
                     in this module.
        @type type: I{int}
        @param value: The data to write into the registry value.
        @type value: I{int}
        """
        permissions = self.vm.remote._winreg.KEY_WRITE
        with self.vm.remote._winreg.OpenKey(self._get_base_key(base_key), sub_key, 0, permissions) as reg_key:
            self.vm.remote._winreg.SetValue(reg_key, name, 0, type, value)

    def enumerate_key(self, base_key, sub_key):
        """
        Allow the user to iterate over values of a given registry key. This method is a generator.
        @param base_key: The base key of the registry value.
        @type base_key: I{str}
        @param sub_key: The path of the registry key, without the base key.
        @type sub_key: I{str}
        @return: A value in the given key.
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
                pass

            finally:
                # Ensure key closing
                key.close()

    def delete_value(self, base_key, sub_key, name):
        """
        Delete a registry value.
        @param base_key: The value's base key
        @type base_key: I{str}
        @param sub_key: The path of the registry key, without the base key.
        @type sub_key: I{str}
        @param name: The name of the value.
        @type name: I{str}
        """
        permissions = self.vm.remote._winreg.KEY_WRITE
        with self.vm.remote._winreg.OpenKey(self._get_base_key(base_key), sub_key, 0, permissions) as reg_key:
            self.vm.remote._winreg.DeleteKeyEx(reg_key, name)
