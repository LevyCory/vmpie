import logging

import vmpie.plugin as plugin
import vmpie.utils as utils
from pyVmomi import vim
from vmpie.decorators import connected


# TODO: Document all plugin methods
class HardwarePlugin(plugin.Plugin):
    """
    Provide basic hardware functionality. This is the most basic wrapper of pyVmomi objects.
    """
    _name = "hardware"
    _os = [plugin.UNIX, plugin.WINDOWS]

    @connected
    def power_on(self):
        """
        Power on the vm and wait for the task to complete.
        :return: None
        """
        logging.info('Powering on vm {vm}'.format(vm=self.vm.name))
        self.vm.pyVmomiVM.PowerOnVM_Task()

    @connected
    def power_off(self):
        """
        Power off the vm and wait for the task to complete.
        :return: None
        """
        logging.info('Powering off vm {vm}'.format(vm=self.vm.name))
        self.vm.pyVmomiVM.PowerOffVM_Task()

    @connected
    def shutdown(self):
        """
        Shutdown the guest of a vm and wait for the task to complete.
        :return: None
        """
        logging.info('Shutdown vm {vm}'.format(vm=self.vm.name))
        self.vm.pyVmomiVM.ShutdownGuest()

    @connected
    def reboot(self):
        """
        Perform reboot of the guest vm (doesn't wait for the task to complete)
        :return: None
        """
        logging.info('Restarting guest in vm {vm}'.format(vm=self.vm.name))
        self.vm.pyVmomiVM.RebootGuest()

    @connected
    def hard_reboot(self):
        """
        Perform a hard reboot of a vm's guest (doesn't wait for the task to complete)
        :return: None
        """
        logging.info('Restarting vm {vm}'.format(vm=self.vm.name))
        self.vm.pyVmomiVM.ResetVM_Task()

    @connected
    def rename(self, new_vm_name):
        """
        Rename a vm and wait for task to complete
        :param new_vm_name: {str} The new vm's name
        :return: None
        """
        logging.info('Renaming vm {vm} to {new_name}'.format(vm=self.vm.name, new_name=new_vm_name))
        self.vm.pyVmomiVM.Rename_Task(new_vm_name)

    @connected
    def clone(self, vm_name, dst_folder, resource_pool_name=None,
              datastore_name=None, power_on=False, as_template=False):
        """
        Clone a vm to a folder and wait for the task to complete.
        :param vm_name: {str} The name of the cloned vm
        :param dst_folder: {str} The name of the destination folder
        :param resource_pool_name: {str} The name of the cloned vm's resource pool
        :param datastore_name: {str} The name of the cloned vm's datastore
        :param power_on: {bool} Whether to power on the cloned vm after creation
        :param as_template: {bool} Whether to clone the vm to a template
        :return: None
        """
        if resource_pool_name:
            # Get resource pool by name
            resource_pool = utils.get_obj_by_name(resource_pool_name,
                                                  [vim.ResourcePool])
        else:
            # Get the current vm's resource pool
            resource_pool = self.vm._pyVmomiVM.resourcePool

        if datastore_name:
            # Get datastore by name
            datastore = utils.get_obj_by_name(datastore_name, [vim.Datastore])
        else:
            # Get the first available datastore
            datastore = self.vm._pyVmomiVM.datastore[0]

        # Create relocation slec
        relocate_spec = vim.vm.RelocateSpec(pool=resource_pool,
                                            datastore=datastore)

        # Create the clone spec
        cloneSpec = vim.vm.CloneSpec(powerOn=power_on, template=as_template,
                                     location=relocate_spec)

        # Get destination folder
        dst_folder = utils.get_obj_by_name(dst_folder, [vim.Folder])

        logging.info('Cloning vm {vm} to {dst_folder}'.format(
            vm=self.vm.name,
            dst_folder=dst_folder.name))

        # Initiate clone
        clone_task = self.vm._pyVmomiVM.Clone(name=vm_name, folder=dst_folder,
                                  spec=cloneSpec)

        # Wait for clone to complete
        utils.wait_for_task(clone_task)

    @connected
    def link_clone(self):
        # TODO: Link clone
        raise NotImplementedError

    def get_os_name(self):
        """
        Get the name of the vm's operating system
        :return: {str} The vm's os name
        """
        return self.vm._pyVmomiVM.config.guestFullName

    def is_off(self):
        """
        Check whether the vm is powered off
        :return: {bool} True if vm is powered off, False otherwise.
        """
        return not self.is_on()

    def is_on(self):
        """
        Checks whether the vm is powered on
        :return: {bool} True if vm is powered on, False otherwise.
        """
        return (self.vm._pyVmomiVM.runtime.powerState == vim.VirtualMachinePowerState.poweredOn)

    def get_network_adapters(self):
        # TODO: Create nic object, and for each nic available on vm return nic object.
        raise NotImplementedError
