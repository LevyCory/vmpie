# ==================================================================================================================== #
# File Name     : registry.py
# Purpose       : Provide a convenient way to perform filesystem related operations on virtual machines.
# Date Created  : 29/06/2018
# Author        : Avital Livshits, Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

from contextlib import contextmanager

import vmpie.plugin as plugin

# ==================================================== CONSTANTS ===================================================== #

PLUGIN_NAME = "registry"
WIN32CON_TYPE_PREFIX = "REG"

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
        self.win32con = self.vm.remote.win32con
        self.win32api = self.vm.remote.win32api

        self._base_keys = {
            "HKCR": self.win32con.HKEY_CLASSES_ROOT,
            "HKLM": self.win32con.HKEY_LOCAL_MACHINE,
            "HKCC": self.win32con.HKEY_CURRENT_CONFIG,
            "HKDD": self.win32con.HKEY_DYN_DATA,
            "HKPD": self.win32con.HKEY_PERFORMANCE_DATA,
            "HKCU": self.win32con.HKEY_CURRENT_USER,
            "HKU": self.win32con.HKEY_USERS,
        }

        # Inject type constants to the plugin
        for attr in dir(self.win32con):
            if attr.startswith(WIN32CON_TYPE_PREFIX):
                setattr(self, attr, getattr(self.win32con, attr))

    @contextmanager
    def _registry_key(self, base_key, sub_key, access_rights):
        """
        A context manager that ensures the proper use of registry handles.
        @param base_key: The base key of the key to open
        @type base_key: I{str}
        @param sub_key: The path of the registry key, without the base key.
        @type sub_key: I{str}
        @param access_rights: The permissions that will be granted to the handle.
        @type access_rights: I{int}
        @return: An open handle to the registry key
        @rtype: I{PyHANDLE}
        """
        base_key = self._base_keys[base_key.upper()]
        handle = self.win32api.RegOpenKeyEx(base_key, sub_key, 0, access_rights)

        yield handle

        self.win32api.RegCloseKey(handle)

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
        with self._registry_key(base_key, sub_key, self.win32con.KEY_ALL_ACCESS) as reg_key:
            return self.win32api.RegQueryValueEx(reg_key, name)

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
        with self._registry_key(base_key, sub_key, self.win32con.KEY_ALL_ACCESS) as reg_key:
            self.win32api.RegSetValueEx(reg_key, name, 0, type, value)

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
        with self._registry_key(base_key, sub_key, self.win32con.KEY_ALL_ACCESS) as reg_key:
            self.win32api.RegDeleteKey(reg_key, name)
