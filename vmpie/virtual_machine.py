__author__ = 'CSI-USER'
from pyVmomi import vim
import os
import logging
import requests

import exceptions
import utils
import consts
import folder  # To prevent import loops
from decorators import is_connected


class VirtualMachine(object):
    def __init__(self, vm_name, guest_username=consts.DEFAULT_GUEST_USERNAME,
                 guest_password=consts.DEFAULT_GUEST_PASSWORD, parent=None,
                 _pyVmomiVM=None):

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

        self._path = ""
        self._datastores = []

        self.hardware = self._Hardware(self)
        self.filesystem = self._Filesystem(self)

    @property
    @is_connected
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

    class _Hardware(object):

        def __init__(self, vm):
            self.vm = vm

        @is_connected
        def power_on(self):
            logging.info('Powering on vm {vm}'.format(vm=self.vm.name))
            self.vm.pyVmomiVM.PowerOnVM_Task()

        @is_connected
        def power_off(self):
            logging.info('Powering off vm {vm}'.format(vm=self.vm.name))
            self.vm.pyVmomiVM.PowerOffVM_Task()

        @is_connected
        def shutdown(self):
            logging.info('Shutdown vm {vm}'.format(vm=self.vm.name))
            self.vm.pyVmomiVM.ShutdownGuest()

        @is_connected
        def reboot(self):
            logging.info('Restarting guest in vm {vm}'.format(vm=self.vm.name))
            self.vm.pyVmomiVM.RebootGuest()

        @is_connected
        def hard_reboot(self):
            logging.info('Restarting vm {vm}'.format(vm=self.vm.name))
            self.vm.pyVmomiVM.ResetVM_Task()

        @is_connected
        def rename(self, new_vm_name):
            logging.info(
                'Renaming vm {vm} to {new_name}'.format(vm=self.vm.name,
                                                        new_name=new_vm_name))
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
            return not (self.vm._pyVmomiVM.runtime.powerState ==
                        vim.VirtualMachinePowerState.poweredOn)

        def is_on(self):
            return (self.vm._pyVmomiVM.runtime.powerState ==
                    vim.VirtualMachinePowerState.poweredOn)

        def get_network_adapters(self):
            pass
            # TODO: Create nic object, and for each nic available on vm return nic object.

    class _Filesystem(object):

        def __init__(self, vm):
            self.vm = vm

        def create_file(self, file_location, file_name, file_content):

            creds = vim.vm.guest.NamePasswordAuthentication(
                username=self.vm.username,
                password=self.vm.password)
            if not file_content:
                file_content = ""

            command = 'echo'
            arguments = 'cmd /c {file_content}  > {file_locations}/{file_name}'. \
                format(file_content=file_content,
                       file_name=file_name,
                       file_location=file_location)

            try:
                utils.run_command_in_vm(self.vm.pyVmomiVM,
                                        command,
                                        arguments,
                                        creds)

            except exceptions.VmwareToolsException:
                logging.error('File will not be created.')
                raise

            except IOError:
                logging.error(
                    'Unable to create file. Check you location and name',
                    exc_info=True)
            except Exception:
                logging.error('An error occurred while creating the file',
                              exc_info=True)

        def delete_file(self):
            pass

        def edit_file(self):
            pass

        def upload_file(self, local_file_path, path_in_vm):
            if utils.is_vmware_tools_running:
                logging.info(
                    'Uploading file to vm {vm}'.format(vm=self.vm.name))

                creds = vim.vm.guest.NamePasswordAuthentication(
                    username=self.vm.username,
                    password=self.vm.password)

                with open(local_file_path, 'rb') as myfile:
                    file_content = myfile.read()

                try:

                    logging.debug(
                        'Uploading file to vm {vm}'.format(vm=self.vm.name))

                    file_attribute = vim.vm.guest.FileManager.FileAttributes()

                    vcenter = utils.get_vcenter()

                    url = vcenter._connection.content.guestOperationsManager.fileManager. \
                        InitiateFileTransportToGuest(self.vm,
                                                     creds,
                                                     path_in_vm,
                                                     file_attribute,
                                                     len(file_content),
                                                     True)

                    resp = requests.put(url, data=file_content, verify=False)

                    if not resp.status_code == consts.SUCCESS_RESPONSE_CODE:
                        logging.info('Successfully uploaded file.')

                    else:
                        logging.error(
                            'Error while uploading file. Response status code: {code}'
                            .format(code=resp.status_code))

                except IOError:
                    logging.error(
                        'Unable to read file {file_path}. Check you path'
                        .format(file_path=local_file_path), exc_info=True)

                except Exception:
                    logging.error('An error occurred while uploading file',
                                  exc_info=True)

            else:
                logging.error('File will not be uploaded.')
                raise exceptions.VmwareToolsException

        def download_file(self):
            pass
