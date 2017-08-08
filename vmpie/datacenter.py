__author__ = 'CSI-USER'

import VmPie
from pyVmomi import vim


class Datacenter(object):

    def __init__(self, datacenter_name):

        self.name = datacenter_name
        self.pyVmomiDatacenter = VmPie.utils.get_obj_by_name(
            name=datacenter_name,
            vimtypes=[vim.Datacenter]
        )

        # Get names of the folders in datacenters
        self._folders = VmPie.folder('vm').folders
        # Get datastores for the datacenter
        self.datastores = [VmPie.datastore(datastore.name) for datastore in self.pyVmomiDatacenter.datastore]

    def add_nfs_datastore(self, name, remote_host, remote_path, read_only=False, username=None, password=None):

        # TODO: self.hosts
        # Get all hosts
        hosts = VmPie.utils.get_objects(vimtypes=[vim.host])

        spec = vim.host.NasVolume.Specification()
        spec.remoteHost = remote_host
        spec.remotePath = remote_path
        spec.localPath = name

        if self.read_only:
            spec.accessMode = "readOnly"
        else:
            spec.accessMode = "readWrite"

        for host in hosts:
            # For each host add NAS datastore
            host.configManager.DatastoreSystem.CreateNasDatastore(spec)

    @property
    def folders(self):
        folders = []
        # Update folders
        self._folders = VmPie.folder('vm').folders
        # Create VmPie.folder object for each folder
        for folder_name in self._folders:
            folders.append(VmPie.folder(folder_name.name))
        # Return folders
        return folders

    def __str__(self):
        return '<Datacenter: {datacenter_name}>'.format(datacenter_name=self.name)

    def __repr__(self):
        return '<Datacenter: {datacenter_name}>'.format(datacenter_name=self.name)
