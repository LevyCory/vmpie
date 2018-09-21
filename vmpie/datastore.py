from pyVmomi import vim
from pyVmomi import vmodl

import utils
import virtual_machine
import vmpie_exceptions


class Datastore(object):

    def __init__(self, datastore_name, _pyVmomiDatastore=None):

        # Name of the datastore
        self.name = datastore_name

        if isinstance(_pyVmomiDatastore, vim.Datastore):
            self._pyVmomiDatastore = _pyVmomiDatastore
        else:
            # Get pyVmomi object
            self.__pyVmomiDatastore = utils.get_obj_by_name(
                name=datastore_name,
                vimtypes=[vim.Datastore]
            )

        self._moId = self._pyVmomiDatastore._moId
        self.type = self._pyVmomiDatastore.summary.type
        # Inner vms list - List of vms is provided by vms() method
        self._vms = []

    @property
    def vms(self):
        # Refreshes all storage related information including free-space,
        # capacity, and detailed usage of virtual machines.
        self._pyVmomiDatastore.RefreshDatastoreStorageInfo()

        for vm in self._pyVmomiDatastore.vm:
            if isinstance(vm, vim.VirtualMachine):
                try:
                    self._vms.append(virtual_machine.VirtualMachine(vm.name, _pyvmomiVm=vm))
                except vmodl.fault.ManagedObjectNotFound:
                    # Handle cases in which a vm is deleted while iterating
                    continue

        return self._vms

    @property
    def free_space(self):
        self._pyVmomiDatastore.RefreshDatastore()
        return self._pyVmomiDatastore.info.freeSpace

    @property
    def capacity(self):
        return self._pyVmomiDatastore.summary.capacity

    def unmount(self):
        try:
            self._pyVmomiDatastore.DestroyDatastore()

        except vim.fault.ResourceInUse:
            pass
            # TODO: Create Resourse in Use exception
        # TODO: Catch no privileges exception

    def refresh(self):
        self._pyVmomiDatastore.RefreshDatastore()

    def rename(self, new_name):
        try:
            self._pyVmomiDatastore.RenameDatastore(newName=new_name)
        except vim.fault.DuplicateName:
            pass
            # TODO: Create exception
        except vim.fault.InvalidName:
            pass
            # TODO: Create exception

    def enter_maintenance_mode(self):
        try:
            self._pyVmomiDatastore.DatastoreEnterMaintenanceMode()
        except vim.fault.InvalidState:
            raise vmpie_exceptions.InvalidStateException(
                "Datastore {datastore_name} is already in maintenance mode.".format(
                    datastore_name=self.name
                )
            )

    def exit_maintenance_mode(self):
        # TODO: Create a task object for async
        try:
            task = self._pyVmomiDatastore.DatastoreExitMaintenanceMode_Task()
        except vim.fault.InvalidState:
            raise vmpie_exceptions.InvalidStateException(
                "Datastore {datastore_name} is not in maintenance mode.".format(
                    datastore_name=self.name
                )
            )

    def __str__(self):
        return '<Datastore: {datastore_name}>'.format(datastore_name=self.name)

    def __repr__(self):
        return '<Datastore: {datastore_name}>'.format(datastore_name=self.name)
