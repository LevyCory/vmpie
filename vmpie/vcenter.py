import logging
import atexit
import time
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
from threading import Thread
import base64

import vmpie
import consts
import utils
from folder import Folder
from virtual_machine import VirtualMachine


class VCenter(object):

    def __init__(self):

        self._connection = None
        self._logged_in = False
        self._user = None
        self._host = None
        self._passwd = None
        self._full_name = None
        self._name = ""
        self._version = None
        self._os = None

    def connect(self, host, user, passwd):
        try:
            self._connection = SmartConnect(
                host=host,
                user=user,
                pwd=passwd
            )

        except vim.fault.InvalidLogin:
                logging.warning("Cannot connect to specified host \
                using given username and password.")
            # TODO: Raise login exception

        except Exception as exc:
            if isinstance(exc, vim.fault.HostConnectFault) \
                    and '[SSL: CERTIFICATE_VERIFY_FAILED' in exc.msg:
                try:
                    import ssl
                    default_context = ssl._create_default_https_context
                    ssl._create_default_https_context = ssl._create_unverified_context
                    self._connection = SmartConnect(
                        host=host,
                        user=user,
                        pwd=passwd
                    )
                    ssl._create_default_https_context = default_context
                except Exception as exc1:
                    raise Exception(exc1)
            else:
                logging.error("Cannot connect to host, due to an error.", exc_info=True)
                # TODO: Raise login exception

        if self._connection:
            atexit.register(Disconnect, self._connection)
            self._logged_in = True
            self._host = host
            self._user = user
            self._passwd = base64.b64encode(passwd)
            self.session_keeper()
            vmpie.set_vcenter(self)

    def is_connected(self):
        if self._logged_in:
            if not self._connection.content.sessionManager.currentSession:
                logging.debug("Session has expired. Renewing session.")
                self.connect(self._host, self._user, self._passwd)

                if self._connection:
                    logging.debug("Renewed session successfully.")
                else:
                    logging.debug("Session renewal failed. True connecting again.")
                    # Raise login exception

            return True
        return False

    def _session_keeper_worker(self):
        while True:
            try:
                self._ping()
            except:
                pass
            finally:
                time.sleep(consts.SESSION_KEEPER_TIMEOUT)

    def session_keeper(self):
        self._life_keeper_thread = Thread(target=self._session_keeper_worker,  args=())
        self._life_keeper_thread.daemon = True
        self._life_keeper_thread.start()

    def _ping(self):
        return self._connection.CurrentTime()

    def disconnect(self):
        self._connection.content.sessionManager.Logout()

    def get_vm(self, vm_name):
        return VirtualMachine(vm_name)

    def get_all_vms(self):
        container_view = self._connection.content.viewManager.CreateContainerView(
            self._connection.content.rootFolder,
            [vim.VirtualMachine],
            True
        )
        children = container_view.view
        vms = []

        for vm in children:
            vms.append(VirtualMachine(vm.name, _pyVmomiVM=vm))

        return vms

    def get_folder(self, folder_name):
        return Folder(folder_name)

    def get_machines_by_folder(self, folder_name):
        return Folder(folder_name).vms

    def backup(self):
        folders = utils._create_folder_tree()
        vm_paths = utils._get_all_vm_paths()

    def __str__(self):
        return '<VCenter: {vc_name}>'.format(vc_name=self.name)

    def __repr__(self):
        return '<VCenter: {vc_name}>'.format(vc_name=self.name)
