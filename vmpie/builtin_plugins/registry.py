# ==================================================================================================================== #
# File Name     : registry.py
# Purpose       : Provide a convenient way to perform filesystem related operations on virtual machines.
# Date Created  : 29/06/2018
# Author        : Avital Livshits, Cory Levy
# Remarks       : In this module there are some technical terms describing certain parts of the Windows Registry.
#                 To use this module you should have a basic understanding of the these terms.
#
#                 base key: The hive key of the windows registry. In the registry itself it can be seen as
#                           the topmost keys like HKEY_CLASSES_ROOT, HKEY_LOCAL_MACHINE and so on. In this module,
#                           the parameter base_key is always the acronym string of those values. For example, if I
#                           want to do something in the HKEY_CURRENT_USER tree, I should pass "HKCU" as the value for
#                           base_key. This is the proper and only acceptable usage of this module.
#
#                 sub key:  The subordinate key is the rest of the registry key's path after the base (hive) key.
#                           If we are reading the key HKCU\Software\Google\Chrome then HKCU is the base key and
#                           "Software\Google\Chrome" is the sub key.
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

from contextlib import contextmanager

import vmpie.plugin as plugin

# ==================================================== CONSTANTS ===================================================== #

PLUGIN_NAME = "registry"
REGISTRY_TYPE_NAMES = (
    'REG_BINARY',
    'REG_DWORD',
    'REG_DWORD_LITTLE_ENDIAN',
    'REG_DWORD_BIG_ENDIAN',
    'REG_EXPAND_SZ',
    'REG_LINK',
    'REG_MULTI_SZ',
    'REG_NONE',
    'REG_QWORD',
    'REG_QWORD_LITTLE_ENDIAN',
    'REG_SZ'
)

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
        self._win32con = self.vm.remote.win32con
        self._win32api = self.vm.remote.win32api

        self._base_keys = {
            "HKCR": self._win32con.HKEY_CLASSES_ROOT,
            "HKLM": self._win32con.HKEY_LOCAL_MACHINE,
            "HKCC": self._win32con.HKEY_CURRENT_CONFIG,
            "HKDD": self._win32con.HKEY_DYN_DATA,
            "HKPD": self._win32con.HKEY_PERFORMANCE_DATA,
            "HKCU": self._win32con.HKEY_CURRENT_USER,
            "HKU": self._win32con.HKEY_USERS,
        }

        # Inject type constants to the plugin
        for attr in REGISTRY_TYPE_NAMES:
                setattr(self, attr, getattr(self._win32con, attr))

    def _get_base_key(self, base_key):
        """
        Get the corresponding constant for the supplied registry hive key.
        @param base_key: A shortened string that represents a registry base key. For example, "HKCU".
        @type base_key: I{str}
        @return: The constant representing the key on the target machine.
        @rtype: I{int}
        """
        return self._base_keys[base_key.upper()]

    @contextmanager
    def _open_registry_key(self, base_key, sub_key, access_rights):
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
        # Create a handle to the registry key
        base_key = self._get_base_key(base_key)
        handle = self._win32api.RegOpenKeyEx(base_key, sub_key, 0, access_rights)

        # Yield the handle to the context manager for further action
        yield handle

        # Close the registry handle
        self._win32api.RegCloseKey(handle)

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
        with self._open_registry_key(base_key, sub_key, self._win32con.KEY_ALL_ACCESS) as reg_key:
            return self._win32api.RegQueryValueEx(reg_key, name)

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
        with self._open_registry_key(base_key, sub_key, self._win32con.KEY_ALL_ACCESS) as reg_key:
            self._win32api.RegSetValueEx(reg_key, name, 0, type, value)

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
        with self._open_registry_key(base_key, sub_key, self._win32con.KEY_ALL_ACCESS) as reg_key:
            self._win32api.RegDeleteValue(reg_key, name)

    def create_key(self, base_key, sub_key):
        """
        Create a new empty registry key.
        @param base_key: The value's base key.
        @type base_key: I{str}
        @param sub_key: The full path to the value without the base key
        @type sub_key: I{str}
        """
        handle = None

        try:
            # Create the registry key
            handle = self._win32api.RegCreateKey(self._get_base_key(base_key), sub_key)

        except Exception:
            raise WindowsError("Could not create registry key")

        # Ensure proper closure of registry key
        finally:
            if handle is not None:
                self._win32api.RegCloseKey(handle)


    def delete_key(self, base_key, sub_key):
        """
        Delete a registry key along with all of it's values
        @param base_key: The key's base key.
        @type base_key: I{str}
        @param sub_key: The key's full path with the base key omitted.
        @type sub_key: I{str}
        """
        self._win32api.RegDeleteKey(self._get_base_key(base_key), sub_key)

    def enumerate_key(self, base_key, sub_key):
        """
        Enumerate a registry key. This is a generator for easy iteration over registry keys.
        @param base_key: The key's base key.
        @type base_key: I{str}
        @param sub_key: The key's full path with the base key omitted.
        @type sub_key: I{str}
        @return: Values that are stored in the supplied key.
        @rtype: Tuple
        """
        index = -1
        with self._open_registry_key(base_key, sub_key, self._win32con.KEY_ALL_ACCESS) as reg_key:
            # Iterate over the registry key
            while True:
                try:
                    index += 1
                    # Yield each registry value
                    yield self._win32api.RegEnumKey(reg_key, index)
                except Exception:
                    # Either an exception occurred or the we've reached the end of the registry key.
                    break

    def read_key(self, base_key, sub_key):
        """
        Read a registry key. Get all values of a registry key at once.
        @param base_key: The key's base key.
        @type base_key: I{str}
        @param sub_key: The key's full path with the base key omitted.
        @type sub_key: I{str}
        @return: The key's values.
        @rtype: I{list}
        """
        values = []

        for value in self.enumerate_key(base_key, sub_key):
            values.append(value)

        return values
