import os

from pyVmomi import vim

import utils
import consts
import folder  # To prevent import loops
from vmpie import _plugins
from vcenter import connected
from hardware import HardwarePlugin


class VirtualMachine(object):
    """
    Represent a virtual machine.
    """
    def __init__(self, vm_name, guest_username=consts.DEFAULT_GUEST_USERNAME,
                 guest_password=consts.DEFAULT_GUEST_PASSWORD, parent=None,
                 _pyVmomiVM=None):
        """
        @summary: Initiate the virtual machine object.
        @param vm_name: The name of the virtual machine on ESX server.
        @type vm_name: string
        @param guest_username: The user account name of the guest OS.
        @type guest_username: string
        @param guest_password: The login password to the guest OS.
        @type guest password: string
        @param parent: ???
        @type parent: ???
        """
        self.name = vm_name
        self._parent = None

        if isinstance(parent, folder.Folder):
                self._parent = parent

        elif isinstance(parent, vim.Folder):
            self._parent = folder.Folder(folder_name=parent.name, _pyVmomiFolder=parent)

        if isinstance(_pyVmomiVM, vim.VirtualMachine):
            self._pyVmomiVM = _pyVmomiVM

        else:
            self._pyVmomiVM = utils.get_obj_by_name(
                name=vm_name,
                vimtypes=[vim.VirtualMachine],
                folder=self._parent._pyVmomiFolder if self._parent else None
            )

        self._moid = self._pyVmomiVM._moId
        self.username = guest_username
        self.password = guest_password

        try:
            self.template = self._pyVmomiVM.config.template
            self.os_name = self._pyVmomiVM.config.guestFullName
            self._vmx = self._pyVmomiVM.config.files.vmPathName
        except AttributeError:
            # TODO: Usually cause when a vm doesnt exist anymore. What should we do?
            pass

        # Hardware must be a part of the object
        self.hardware = HardwarePlugin(self)

        # Load collected plugins
        for plugin in _plugins:
            if self._is_plugin_compatible(plugin):
                self.load_plugin(plugin)

        self._path = ""
        self._datastores = []

    def _is_plugin_compatible(self, plugin):
        """

        @param plugin:
        @return:
        """
        return self.hardware.get_os_name() in plugin._os

    def load_plugin(self, plugin):
        """
        @summary: Load a plugin
        """
        setattr(self, plugin._name, plugin)

    @property
    @connected
    def parent(self):
        if not isinstance(self._parent, folder.Folder) or self._parent._moId != self._pyVmomiVM.parent._moId:
            self._parent = folder.Folder(folder_name=self._pyVmomiVM.parent.name, _pyVmomiFolder=self._pyVmomiVM.parent)
        return self._parent

    @property
    def path(self):
        path = []
        current_object = self
        while current_object.parent:
            path.append(current_object.name)
            current_object = current_object.parent
        self._path = os.path.join(*path[::-1])
        return self._path

    def __str__(self):
        return '<Vm: {vm_name}>'.format(vm_name=self.name)

    def __repr__(self):
        return '<Vm: {vm_name}>'.format(vm_name=self.name)
