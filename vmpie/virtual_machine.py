# ==================================================================================================================== #
# File Name     : virtual_machine.py
# Purpose       : Provide the object that represents virtual machines.
# Date Created  : 12/11/2017
# Author        : Avital Livshits, Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

import os

from pyVmomi import vim

import consts
import folder  # To prevent import loops
import utils
import vmpie
from decorators import connected
from vmpie.builtin_plugins.remote import RemotePlugin


# ===================================================== CONSTS ====================================================== #

OPERATING_SYSTEMS = {
    'asianux3_64Guest': 'posix',
    'asianux3Guest': 'posix',
    'asianux4_64Guest': 'posix',
    'asianux4Guest': 'posix',
    'centos64Guest': 'posix',
    'centosGuest': 'posix',
    'darwin64Guest': 'posix',
    'darwinGuest': 'posix',
    'debian4_64Guest': 'posix',
    'debian4Guest': 'posix',
    'debian5_64Guest': 'posix',
    'debian5Guest': 'posix',
    'dosGuest': 'posix',
    'eComStationGuest': 'posix',
    'freebsd64Guest': 'posix',
    'freebsdGuest': 'posix',
    'mandriva64Guest': 'posix',
    'mandrivaGuest': 'posix',
    'netware4Guest': 'posix',
    'netware5Guest': 'posix',
    'netware6Guest': 'posix',
    'nld9Guest': 'posix',
    'oesGuest': 'posix',
    'openServer5Guest': 'posix',
    'openServer6Guest': 'posix',
    'oracleLinux64Guest': 'posix',
    'oracleLinuxGuest': 'posix',
    'os2Guest': 'posix',
    'other24xLinux64Guest': 'posix',
    'other24xLinuxGuest': 'posix',
    'other26xLinux64Guest': 'posix',
    'other26xLinuxGuest': 'posix',
    'otherGuest': 'posix',
    'otherGuest64': 'posix',
    'otherLinux64Guest': 'posix',
    'otherLinuxGuest': 'posix',
    'redhatGuest': 'posix',
    'rhel2Guest': 'posix',
    'rhel3_64Guest': 'posix',
    'rhel3Guest': 'posix',
    'rhel4_64Guest': 'posix',
    'rhel4Guest': 'posix',
    'rhel5_64Guest': 'posix',
    'rhel5Guest': 'posix',
    'rhel6_64Guest': 'posix',
    'rhel6Guest': 'posix',
    'sjdsGuest': 'posix',
    'sles10_64Guest': 'posix',
    'sles10Guest': 'posix',
    'sles11_64Guest': 'posix',
    'sles11Guest': 'posix',
    'sles64Guest': 'posix',
    'slesGuest': 'posix',
    'solaris10_64Guest': 'posix',
    'solaris10Guest': 'posix',
    'solaris6Guest': 'posix',
    'solaris7Guest': 'posix',
    'solaris8Guest': 'posix',
    'solaris9Guest': 'posix',
    'suse64Guest': 'posix',
    'suseGuest': 'posix',
    'turboLinux64Guest': 'posix',
    'turboLinuxGuest': 'posix',
    'ubuntu64Guest': 'posix',
    'ubuntuGuest': 'posix',
    'unixWare7Guest': 'posix',
    'win2000AdvServGuest': 'nt',
    'win2000ProGuest': 'nt',
    'win2000ServGuest': 'nt',
    'win31Guest': 'nt',
    'win95Guest': 'nt',
    'win98Guest': 'nt',
    'windows7_64Guest': 'nt',
    'windows7Guest': 'nt',
    'windows7Server64Guest': 'nt',
    'winLonghorn64Guest': 'nt',
    'winLonghornGuest': 'nt',
    'winMeGuest': 'nt',
    'winNetBusinessGuest': 'nt',
    'winNetDatacenter64Guest': 'nt',
    'winNetDatacenterGuest': 'nt',
    'winNetEnterprise64Guest': 'nt',
    'winNetEnterpriseGuest': 'nt',
    'winNetStandard64Guest': 'nt',
    'winNetStandardGuest': 'nt',
    'winNetWebGuest': 'nt',
    'winNTGuest': 'nt',
    'winVista64Guest': 'nt',
    'winVistaGuest': 'nt',
    'winXPHomeGuest': 'nt',
    'winXPPro64Guest': 'nt',
    'winXPProGuest': 'nt',
    'windows8Server64Guest': 'nt',
}

# ===================================================== CLASSES ====================================================== #


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

        # TODO: Find a better way to do that
        self.remote = RemotePlugin(self)

        # Load collected plugins if they're compatible with the guest OS
        for plugin in vmpie._plugins:
            if self._is_plugin_compatible(plugin):
                self.load_plugin(plugin)

        self._path = ""
        self._datastores = []

    @property
    def ip_addresses(self):
        """
        A list of machine ip addresses
        """
        addresses = []
        for nic in self._pyVmomiVM.guest.net:
            addresses.append(nic.ipAddress[1])

        return addresses

    def _is_plugin_compatible(self, plugin):
        """
        Check if a plugin is compatible with the guest OS.
        @param plugin: The plugin to validate
        @type plugin: I{vmpie.plugin.Plugin}
        @return: Whether the plugin is compatible with the guest OS or not.
        @rtype: I{boolean}
        """
        if not OPERATING_SYSTEMS.get(self._pyVmomiVM.summary.config.guestId):
            raise Exception("Operating system unknown: {}.".format(self._pyVmomiVM.summary.config.guestId))

        return OPERATING_SYSTEMS.get(self._pyVmomiVM.summary.config.guestId) in plugin._os

    def load_plugin(self, plugin):
        """
        Load a plugin to the VM object.
        @param plugin: The plugin to load.
        @type plugin: I{vmpie.plugin.Plugin}
        """
        setattr(self, plugin._name, plugin(self))

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
