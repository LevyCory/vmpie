from pyVmomi import vim
import os

# To prevent import loops
import virtual_machine
import utils


class Folder(object):

    def __init__(self, folder_name, _pyVmomiFolder=None):

        self.name = folder_name
        if isinstance(_pyVmomiFolder, vim.Folder):
            self._pyVmomiFolder = _pyVmomiFolder
        else:
            self._pyVmomiFolder = utils.get_obj_by_name(
                name=folder_name,
                vimtypes=[vim.Folder]
            )

        if isinstance(self._pyVmomiFolder.parent, vim.Folder):
            self._parent = self._pyVmomiFolder.parent.name
        else:
            self._parent = None

        self._moId = self._pyVmomiFolder._moId
        self._vms = []
        self._folders = []
        self._path = ""

    @property
    def parent(self):
        if isinstance(self._parent, str):
            self._parent = Folder(self._parent)
        return self._parent

    @property
    def folders(self):
        for folder in self._pyVmomiFolder.childEntity:
            if isinstance(folder, vim.Folder):
                self._folders.append(Folder(folder.name))
        return self._folders

    @property
    def vms(self):
        self._vms = []
        for vm in self._pyVmomiFolder.childEntity:
            if isinstance(vm, vim.VirtualMachine):
                self._vms.append(virtual_machine.VirtualMachine(vm.name))
        return self._vms

    @property
    def path(self):
        path = []
        current_object = self
        while current_object.parent:
            path.append(current_object.name)
            current_object = current_object.parent
        self._path = os.path.join(*path[::-1])
        return self._path

    def clone(self):
        pass

    def move(self, destination_folder_name):
        destination = Folder(destination_folder_name)
        destination._pyVmomiFolder.MoveIntoFolder_Task([self._pyVmomiFolder])
        self._path = None

    def destroy(self):
        self._pyVmomiFolder.Destroy_Task()

    def rename(self, name):
        self._pyVmomiFolder.renameTask(newName=name)

    def create_subfolder(self, subfolder_name):
        self._pyVmomiFolder.CreateFolder(name=subfolder_name)

    def __str__(self):
        return '<Folder: {folder_name}>'.format(folder_name=self.name)

    def __repr__(self):
        return '<Folder: {folder_name}>'.format(folder_name=self.name)
