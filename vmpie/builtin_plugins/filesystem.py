# ==================================================================================================================== #
# File Name     : filesystem.py
# Purpose       : Provide a convenient way to perform filesystem related operations on virtual machines.
# Date Created  : 11/11/2017
# Author        : Avital Livshits, Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

import hashlib
import logging
import requests

from pyVmomi import vim

from vmpie import consts
from vmpie import utils
from vmpie import vmpie_exceptions
import vmpie.plugin as plugin

# ==================================================== CONSTANTS ===================================================== #
# ===================================================== CLASSES ====================================================== #


class FilesystemPlugin(plugin.Plugin):
    """
    Filesystem operations on virtual machines.
    """
    _name = "filesystem"
    _os = [plugin.UNIX, plugin.WINDOWS]

    def exists(self, path):
        """
        Check if a path exists on the target machine.
        @param path: The path to check
        @type path: I{str}
        @return: Whether the path exists or not
        @rtype: I{bool}
        """
        return self.vm.remote.os.path.exists(path)

    def create_file(self, path, content=""):
        """
        Create a file on the target machine.
        @param path: The path of the file to create
        @type path: I{str}
        @param content: The content of the file to create
        @type content: I{str}
        """
        with self.open(path, "w") as remote_file:
            remote_file.write(content)

    def is_file(self, path):
        """
        Check if a path is a file on the target machine.
        @param path: The path to check
        @type path: I{str}
        @return: Whether the path is a file or not
        @rtype: I{bool}
        """
        return self.vm.remote.os.path.isfile(path)

    def is_directory(self, path):
        """
        Check if a path is a directory on the target machine.
        @param path: The path to check
        @type path: I{str}
        @return: Whether the path is a directory or not
        @rtype: I{bool}
        """
        return self.vm.remote.os.path.isdir(path)

    def remove(self, path):
        """
        Remove the file or folder located at I{path}
        @param path: The path to remove
        @type path: I{str}
        """
        if self.vm.filesystem.is_file(path):
            self.vm.remote.os.remove(path)
        else:
            self.vm.remote.shutil.rmtree(path)

    def create_directory(self, path, recursive=True):
        """
        Create a directory on the target machine.
        @param path: The path of the directory to create
        @type path: I{str}
        @param recursive: Whether or not to ensure the creation of all the directories in the given path
        @type recursive: I{bool}
        """
        if recursive:
            self.vm.remote.os.makedirs(path)
        else:
            self.vm.remote.os.mkdir(path)

    def get_file_md5(self, path):
        """
        Calcualte a file's MD5 hash.
        @param path: The path of the file to digest.
        @type path: I{str}
        @return: The MD5 digest of the file
        @rtype: I{str}
        """
        with self.open(path, "rb") as remote_file:
            data = remote_file.read()

        return hashlib.md5(data).hexdigest()

    def get_file_checksum(self, path):
        """

        @param path:
        @return:
        """
        raise NotImplementedError

    def open(self, path, mode):
        """
        Open a file on the remote machine. Behaves exactly like python's builtin I{open} function.
        @param path: The path of the file to open
        @type path: I{str}
        @param mode: The mode to open the file in.
        @type mode: I{str}
        @return: The opened file.
        @rtype: I{vmpie.remote._RemoteFile}
        """
        return self.vm.remote.builtin("open", path, mode)

    def offline_create_file(self, file_location, file_name, file_content):

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

        except vmpie_exceptions.VMWareToolsException:
            logging.error('File will not be created.')
            raise

        except IOError:
            logging.error(
                'Unable to create file. Check you location and name',
                exc_info=True)
        except Exception:
            logging.error('An error occurred while creating the file',
                          exc_info=True)

    def offline_upload_file(self, local_file_path, path_in_vm):
        if utils.is_vmware_tools_running:
            logging.info('Uploading file to vm {vm}'.format(vm=self.vm.name))

            creds = vim.vm.guest.NamePasswordAuthentication(
                username=self.vm.username,
                password=self.vm.password)

            with open(local_file_path, 'rb') as myfile:
                file_content = myfile.read()

            try:

                logging.debug('Uploading file to vm {vm}'.format(vm=self.vm.name))

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
                    logging.error('Error while uploading file. Response status code: {code}'.format(
                        code=resp.status_code))

            except IOError:
                logging.error('Unable to read file {file_path}. Check you path'.format(
                    file_path=local_file_path), exc_info=True)

            except Exception:
                logging.error('An error occurred while uploading file', exc_info=True)

        else:
            logging.error('File will not be uploaded.')
            raise vmpie_exceptions.VMWareToolsException

    def download_file(self):
        pass
