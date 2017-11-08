import logging

import requests
from pyVmomi import vim
from vmpie import consts
from vmpie import utils
from vmpie import vmpie_exceptions
import vmpie.plugin as plugin
from remote import _RemoteFile


# TODO: Document all plugin methods
class FilesystemPlugin(plugin.Plugin):
    """
    Filesystem operations for windows systems
    """
    _name = "filesystem"
    _os = [plugin.UNIX, plugin.WINDOWS]

    def exists(self, path):
        """

        @param path:
        @return:
        """
        return self.vm.remote.os.path.exists(path)

    def create_file(self, path, content=""):
        """

        @param path:
        @param content:
        @return:
        """
        command = "open({path}, 'w') as f; f.write({data}); f.close()".format(path=path, data=content)
        self.vm.remote.evaluate(command)

    def is_file(self, path):
        """

        @param path:
        @return:
        """
        return self.vm.remote.os.path.isfile(path)

    def is_directory(self, path):
        """

        @param path:
        @return:
        """
        return self.vm.remote.os.path.isdir(path)

    def remove(self, path):
        """

        @param path:
        @return:
        """
        if self.vm.filesystem.is_file(path):
            self.vm.remote.os.remove(path)
        else:
            self.vm.remote.shutil.rmtree(path)

    def create_directory(self, path, recursive=True):
        """

        @param path:
        @param recursive:
        @return:
        """
        if recursive:
            self.vm.remote.os.makedirs(path)
        else:
            self.vm.remote.os.mkdir(path)

    def get_file_md5(self, path):
        """

        @param path:
        @return:
        """
        raise NotImplementedError

    def get_file_checksum(self, path):
        """

        @param path:
        @return:
        """
        raise NotImplementedError

    def open(self, path, mode):
        """

        @param path:
        @param mode:
        @return:
        """
        return _RemoteFile(path, mode, self.vm._pyro_daemon)

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

    def delete_file(self):
        pass

    def edit_file(self):
        pass

    def upload_file(self, local_file_path, path_in_vm):
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

