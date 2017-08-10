from pyVmomi import vim
from pyvmomi_tools import cli
import time
import logging

import vmpie_exceptions
import folder
import vcenter
import consts


def get_vcenter():
    if isinstance(__import__("vmpie").vcenter, vcenter.VCenter):
        return __import__("vmpie").vcenter
    raise vmpie_exceptions.NotConnectedException


def update_stub(object):
    vcenter = get_vcenter()
    object._stub.cookie = vcenter._connection._stub.cookie


def get_obj_by_name(name=None, vimtypes=[], folder=None):
    obj = None
    vcenter = get_vcenter()

    if folder is not None:
        folder = get_obj_by_name(folder, [vim.Folder])
    else:
        folder = vcenter._connection.content.rootFolder

    container = vcenter._connection.content.viewManager.CreateContainerView(
        container=folder,
        type=vimtypes,
        recursive=True
    )

    for c in container.view:
        if name is not None:
            if c.name == name:
                obj = c
                break
        else:
            obj = c
            break

    if obj is None:
        raise vmpie_exceptions.ObjectNotFoundException

    return obj


def get_obj(vimtypes=[], name=None):
    try:
        vcenter = get_vcenter()
        folder = vcenter._connetion.content.rootFolder
        obj = None
        container = vcenter._connection.content.viewManager.CreateContainerView(
            container=folder,
            type=vimtypes,
            recursive=True)

        for c in container.view:

            if name:
                if c.name == name:
                    obj = c
                    break
            else:
                obj = c
                break

        return obj

    except AttributeError:
        raise vmpie_exceptions.NotConnectedException


def get_objects(vimtypes=[]):
    try:
        vcenter = get_vcenter()
        folder = vcenter._connection.content.rootFolder
        container = vcenter._connection.content.viewManager.CreateContainerView(
            container=folder,
            type=vimtypes,
            recursive=True)

        return container.view

    except AttributeError:
        raise vmpie_exceptions.NotConnectedException


def is_vmware_tools_running(vm):
    tools_status = vm._pyVmomiVM.guest.toolsStatus
    if tools_status == 'toolsNotInstalled' or tools_status == 'toolsNotRunning':
        logging.warning("VmWare tools are either not running or not installed.")
        return False

    return True


def run_command_in_vm(vm, command, arguments, credentials):
    vcenter = get_vcenter()

    # Verify that VmWare tools are running
    if is_vmware_tools_running(vm):
        try:
            pm = vcenter._connection.content.guestOperationsManager.processManager
            program_spec = vim.vm.guest.ProcessManager.ProgramSpec(
                programPath=command,
                arguments=arguments
            )
            res = pm.StartProgramInGuest(vm, credentials, program_spec)
            return res

        except AttributeError:
            raise vmpie_exceptions.NotConnectedException
    else:
        raise vmpie_exceptions.VmwareToolsException


def _create_folder_tree(root_folder=None):
    vcenter = get_vcenter()
    folders = {}

    if root_folder is None:
        # What if multiple datacenters are available? childEntity[0]...
        root_folder = folder.Folder('vm',
                                    _pyVmomiFolder=vcenter._connection.content.rootFolder.childEntity[0].vmFolder)

    elif isinstance(root_folder, vim.Folder):
        root_folder = folder.Folder(root_folder.name, _pyVmomiFolder=root_folder)
    elif isinstance(root_folder, str):
        root_folder = folder.Folder(root_folder)

    _get_folders_tree(root_folder, folders)

    return folders


def _get_folders_tree(current_folder, folders):
    folders[current_folder] = {}

    for child in current_folder.folders:
        folders[current_folder.name][child.name] = {}
        _get_folders_tree(child, folders[current_folder.name])


def _get_all_vm_paths():
    vcenter = get_vcenter()
    paths = {}
    vms = vcenter.get_all_vms()

    for vm in vms:
        paths[vm.name] = vm.hardware.get_vmx()

    return paths


def wait_with_spinner(condition, argument, msg):
    while condition(argument):
        cli.cursor.spinner(msg)
        time.sleep(consts.SPINNER_SLEEP)


def bytes_to_human(size, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P']:
        if abs(size) < 1024.0:
            return "%3.1f%s%s" % (size, unit, suffix)
        size /= 1024
    return "%.1f%f%f" % (size, unit, suffix)
