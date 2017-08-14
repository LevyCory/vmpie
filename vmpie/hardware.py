import logging

from pyVmomi import vim

from plugin import Plugin
from vcenter import connected


# TODO: Document all plugin methods
class HardwarePlugin(Plugin):
    """
    Provide basic hardware functionality. This is the most basic wrapper of pyVmomi objects.
    """
    _name = "hardware"
    _os = ["nt", "unix"]

    @connected
    def power_on(self):
        logging.info('Powering on vm {vm}'.format(vm=self.vm.name))
        self.vm.pyVmomiVM.PowerOnVM_Task()

    @connected
    def power_off(self):
        logging.info('Powering off vm {vm}'.format(vm=self.vm.name))
        self.vm.pyVmomiVM.PowerOffVM_Task()

    @connected
    def shutdown(self):
        logging.info('Shutdown vm {vm}'.format(vm=self.vm.name))
        self.vm.pyVmomiVM.ShutdownGuest()

    @connected
    def reboot(self):
        logging.info('Restarting guest in vm {vm}'.format(vm=self.vm.name))
        self.vm.pyVmomiVM.RebootGuest()

    @connected
    def hard_reboot(self):
        logging.info('Restarting vm {vm}'.format(vm=self.vm.name))
        self.vm.pyVmomiVM.ResetVM_Task()

    @connected
    def rename(self, new_vm_name):
        logging.info('Renaming vm {vm} to {new_name}'.format(vm=self.vm.name, new_name=new_vm_name))
        self.vm.pyVmomiVM.Rename_Task(new_vm_name)

    def clone(self):
        # TODO: Clone
        pass

    def link_clone(self):
        # TODO: Link clone
        pass

    def get_os_name(self):
        return self.vm._pyVmomiVM.config.guestFullName

    def is_off(self):
        return not (self.vm._pyVmomiVM.runtime.powerState == vim.VirtualMachinePowerState.poweredOn)

    def is_on(self):
        return (self.vm._pyVmomiVM.runtime.powerState == vim.VirtualMachinePowerState.poweredOn)

    def get_network_adapters(self):
        pass
        # TODO: Create nic object, and for each nic available on vm return nic object.
