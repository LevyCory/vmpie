# ==================================================================================================================== #
# File Name     : process.py
# Purpose       : Provides processing operations on virtual machines.
# Date Created  : 11/12/2017
# Author        : Avital Livshits, Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

from pyVmomi import vim

from vmpie import consts
from vmpie import utils
from vmpie import vmpie_exceptions
import vmpie.plugin as plugin
from remote import _RemoteFile

# ==================================================== CONSTANTS ===================================================== #
PARAM_INCORRECT_ERRNO = 87
# ===================================================== CLASSES ====================================================== #


class ProcessPlugin(plugin.Plugin):
    """
    Filesystem operations on virtual machines.
    """
    _name = "process"
    _os = [plugin.WINDOWS]

    def __get_user_token(self, ps='explorer.exe'):
        return self.__get_logged_on_user_token(
            tokenAccess=self.vm.remote.win32security.TOKEN_QUERY | \
                        self.vm.remote.win32security.TOKEN_DUPLICATE | \
                        self.vm.remote.win32security.TOKEN_ASSIGN_PRIMARY,
            ps=ps
        )

    def __get_logged_on_user_token(self, tokenAccess, ps='explorer.exe'):
        """
        Retrieves a the token of the logged on user.
        @param tokenAccess: The required access token to open  the specified process (ps)
        @type tokenAccess: I{A bitwise of win32security.TOKEN_* options}
        @param ps: The process to get the user token from.
        @type ps: I{str}
        @return: A handle to the user token
        @rtype: I{PyHandle}
        """
        proc = self.get_process_by_name(ps)
        if proc:
            return self.vm.remote.win32security.OpenProcessToken(proc.handle, tokenAccess)

        raise KeyError("{ps} was not found among running processes.".format(ps=ps))

    def get_process_by_name(self, ps):
        # TODO: Check handleWrapper and Popen passing through Pyro4
        """
        Retrieves a remote process handle from a virtual machine by name.
        @param ps: The process name
        @type ps: I{str}
        @return: The process handle (if it exists)
        @rtype: I{Popen}
        """
        def _get_process_by_name(ps):
            import win32api
            import win32con
            import pywintypes
            import win32com.client
            import pythoncom

            pythoncom.CoInitializeEx(0)
            mgmt = win32com.client.GetObject('winmgmts:')

            # Get all processes with the given name
            process_list = mgmt.ExecQuery("SELECT * from Win32_Process where Caption = {ps}".format(ps=ps))
            if process_list:
                # Get the process PID (if there are many, select the first one)
                pid = process_list[0].Properties_('ProcessId').Value
                try:
                    # Get the process
                    proc = win32api.OpenProcess(
                        win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                        False,
                        pid
                    )
                    # HandleWrapper??
                    return proc

                except pywintypes.error as e:
                    if e.winerror == PARAM_INCORRECT_ERRNO:
                        return None
                    else:
                        raise
            pythoncom.CoUninitialize()

        return self.vm.remote.teleport(_get_process_by_name)(ps)

    def get_process_by_pid(self, pid):
        # TODO: Check handleWrapper and Popen passing through Pyro4
        """
        Retrieves a remote process handle from a virtual machine by name.
        @param ps: The process name
        @type ps: I{str}
        @return: The process handle (if it exists)
        @rtype: I{Popen}
        """
        def _get_process_by_pid(pid):
            import win32api
            import win32con
            import pywintypes
            import win32com.client
            import pythoncom

            pythoncom.CoInitializeEx(0)
            mgmt = win32com.client.GetObject('winmgmts:')

            # Get all processes with the given PID
            process_list = mgmt.ExecQuery("SELECT * from Win32_Process where ProcessId = {pid}".format(pid=pid))
            if process_list:
                try:
                    # Get process
                    proc = win32api.OpenProcess(
                        win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                        False,
                        pid
                    )
                    # HandleWrapper??
                    return proc

                except pywintypes.error:
                    return None

            pythoncom.CoUninitialize()

        return self.vm.remote.teleport(_get_process_by_pid)(pid)

    def run(self, command, async=False, as_admin=False, daemon=True):
        """
        Run a command in the virtual machine.
        @param command: The command to run
        @type command: I{str}
        @param async: Whether to wait for the command completion
        @type async: I{bool}
        @param as_admin: Whether to run as an admin
        @type as_admin: I{bool}
        @param as_admin: Whether to run in the background (daemon)
        @type as_admin: I{bool}
        @return: The remote process (if async=True), otherwise the return code & output.
        @rtype: I{_RemotePopen (if async=True), otherwise (int, str)}
        """
        # Determine as which user to run the command as
        if as_admin:
            ps = 'winlogon.exe'
        else:
            ps = 'explorer.exe'

        # Create remote Popen
        remote_popen = _RemotePopen(
            command=command,
            user_token=self.__get_user_token(ps=ps),
            sdtout=self.vm.remote.subprocess.PIPE,
            stderr=self.vm.remote.subprocess.STDOUT,
            shell=False,
            startup_info=self._create_startup_info(None, daemon),
            cwd=None,
            env=self.vm.env.get_user_environment_block(ps)
        )

        if async:
            return remote_popen

        # Wait for command completion
        output = remote_popen.stdout.read()
        return_code = remote_popen.wait()

        return return_code, output

    def kill_process(self, pid):
        """
        Kill a process by PID.
        @param pid: The process PID
        @type pid: I{int}
        """
        # Get process by pid
        proc = self.vm.remote.win32api.OpenProcess(self.vm.remote.win32com.PROCESS_ALL_ACCESS,
                                                   False,
                                                   pid)
        # Kill process
        self.vm.remote.win32process.TerminateProcess(proc, 0)