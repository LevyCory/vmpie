# ==================================================================================================================== #
# File Name     : process.py
# Purpose       : Provides processing operations on virtual machines.
# Date Created  : 11/12/2017
# Author        : Avital Livshits, Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

import os
import random

from pyVmomi import vim

from vmpie import consts
from vmpie import utils
from vmpie import vmpie_exceptions
import vmpie.plugin as plugin

# ==================================================== CONSTANTS ===================================================== #

PARAM_INCORRECT_ERRNO = 87
PIPE_NAME = r'\\.\pipe\vmpie-{}'
# ===================================================== CLASSES ====================================================== #


class WindowsProcessPlugin(plugin.Plugin):
    """
    Process operations on Windows virtual machines.
    """
    _name = "process"
    _os = [plugin.WINDOWS]

    def __get_user_token(self, ps='explorer.exe'):
        return self.__get_logged_on_user_token(
            tokenAccess=self.vm.remote.win32security.TOKEN_QUERY |
                        self.vm.remote.win32security.TOKEN_DUPLICATE |
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

    def get_process_by_name(self, ps_name):
        """
        Retrieves a remote process handle from a virtual machine by name.
        @param ps: The process name
        @type ps: I{str}
        @return: The process handle (if it exists)
        @rtype: I{Popen}
        """
        def _get_process_by_name(ps_name):
            import win32api
            import win32con
            import pywintypes
            import win32com.client
            import pythoncom

            pythoncom.CoInitializeEx(0)
            mgmt = win32com.client.GetObject('winmgmts:')

            # Get all processes with the given name
            process_list = mgmt.ExecQuery("SELECT * from Win32_Process where Caption = '{ps_name}'".format(ps_name=ps_name))
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
                    return proc

                except pywintypes.error as e:
                    if e.winerror == PARAM_INCORRECT_ERRNO:
                        return None
                    else:
                        raise
            pythoncom.CoUninitialize()

        return self.vm.remote.teleport(_get_process_by_name)(ps_name)

    def get_process_by_pid(self, pid):
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
                    return proc

                except pywintypes.error:
                    return None

            pythoncom.CoUninitialize()

        return self.vm.remote.teleport(_get_process_by_pid)(pid)

    def _is_admin(self):
        try:
            return self.vm.remote.ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

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
        if as_admin and not self._is_admin():
            # Get the user token from wht winlogon.exe process
            usertoken = self.__get_user_token(ps='winlogon.exe')

        # TODO: Create custom Popen, with token injection

        #usertoken = self.__get_user_token(ps=ps)
        # Create remote Popen
        remote_popen = self.vm.remote.subprocess.Popen(
            args=command,
            stdout=self.vm.remote.subprocess.PIPE,
            stderr=self.vm.remote.subprocess.STDOUT,
            shell=False,
            # TODO: Determine why startup_info stops popen from running
            #startup_info=self._create_startup_info(None, daemon),
            cwd=None,
            #env=self.vm.env.get_user_environment_block(ps)
        )

        if async:
            return remote_popen

        # Wait for command completion
        output = remote_popen.stdout.read()
        return_code = remote_popen.wait()

        return output, return_code

    def run_as_user(self, command, args, username=None, password=None,
                    domain=None, daemon=False):
        if not (username or password or domain):
            # Run as currently logged on user
            usertoken = self.__get_user_token(ps='explorer.exe')

        else:
            # Get user's token
            usertoken = self.vm.remote.win32security.LogonUser(
                username, domain, password,
                self.vm.remote.win32con.LOGON32_LOGON_INTERACTIVE,
                self.vm.remote.win32con.LOGON32_PROVIDER_DEFAULT,
            )

        sids = [self._get_current_sid()]

        if username and password:
            sids.append(self._lookup_sid(domain, username))

        # Create security attributes
        if sids is None:
            sattrs = None
        else:
            sattrs = self._create_security_attributes(
                *sids,
                inherit=True,
                access=self.vm.remote.win32con.PROCESS_ALL_ACCESS
            )

        # # Create pipe handles
        # stdin_handle_read, stdin_handle_write = self.vm.remote.win32pipe.CreatePipe(sattrs, 0)
        # stdout_handle_read, stdout_handle_write = self.vm.remote.win32pipe.CreatePipe(sattrs, 0)
        # stderr_handle_read, stderr_handle_write = self.vm.remote.win32pipe.CreatePipe(sattrs, 0)
        #
        # self.vm.remote.win32api.SetHandleInformation(stdin_handle_write,
        #                                              self.vm.remote.win32con.HANDLE_FLAG_INHERIT,
        #                                              0)
        #
        # self.vm.remote.win32api.SetHandleInformation(stdout_handle_read,
        #                                              self.vm.remote.win32con.HANDLE_FLAG_INHERIT,
        #                                              0)
        #
        # self.vm.remote.win32api.SetHandleInformation(stderr_handle_read,
        #                                              self.vm.remote.win32con.HANDLE_FLAG_INHERIT,
        #                                              0)
        #

        # Create the named pipes
        stdin_pipe, stdin_name = self._create_named_pipe(sids)
        stdout_pipe, stdout_name = self._create_named_pipe(sids)
        stderr_pipe, stderr_name = self._create_named_pipe(sids)

        # Make sure that the parent process's pipe ends are not inherited
        self.vm.remote.win32api.SetHandleInformation(stdin_pipe,
                                                     self.vm.remote.win32con.HANDLE_FLAG_INHERIT,
                                                     0)
        self.vm.remote.win32api.SetHandleInformation(stdout_pipe,
                                                     self.vm.remote.win32con.HANDLE_FLAG_INHERIT,
                                                     0)
        self.vm.remote.win32api.SetHandleInformation(stderr_pipe,
                                                     self.vm.remote.win32con.HANDLE_FLAG_INHERIT,
                                                     0)

        # Create process's startup info
        startup_info = self._create_startup_info(stdin_name,
                                                 stdout_name,
                                                 stderr_name,
                                                 daemon
        )

        # Create process
        res = self.vm.remote.win32process.CreateProcessAsUser(
            usertoken, command, args, sattrs, None, True,
            self.vm.remote.win32con.CREATE_NEW_CONSOLE,
            # self.vm.remote.os.environ, self.vm.remote.os.getcwd(),
            None, None,
            startup_info)

        process_handle = res[0]  # The process handle
        res[1].Close()  # Close the thread handle - not relevant
        pid = res[2]  # The pid

        # Connect to the pipes
        self.vm.remote.win32pipe.ConnectNamedPipe(stdin_pipe)
        self.vm.remote.win32pipe.ConnectNamedPipe(stdout_pipe)
        self.vm.remote.win32pipe.ConnectNamedPipe(stderr_pipe)

        # Wait for the process to complete
        # self.vm.remote.win32event.WaitForSingleObject(process_handle, self.vm.remote.win32event.INFINITE)

        # Remember to close the process!
        return pid, process_handle, stdin_pipe, stdout_pipe, stderr_pipe

    def _get_current_sid(self):
        """INTERNAL: get current SID."""
        try:
            token = self.vm.remote.win32security.OpenThreadToken(
                self.vm.remote.win32api.GetCurrentThread(),
                self.vm.remote.win32con.MAXIMUM_ALLOWED, True)
        except:
            token = self.vm.remote.win32security.OpenProcessToken(
                self.vm.remote.win32api.GetCurrentProcess(),
                self.vm.remote.win32con.MAXIMUM_ALLOWED)
        return self.vm.remote.win32security.GetTokenInformation(
            token,
            self.vm.remote.win32security.TokenUser
        )[0]

    def _lookup_sid(self, domain, username):
        """INTERNAL: lookup the SID for a user in a domain."""
        return self.vm.remote.win32security.LookupAccountName(domain, username)[0]

    def _create_security_attributes(self, *sids, **kwargs):
        """INTERNAL: create a SECURITY_ATTRIBUTES structure."""
        inherit = kwargs.get('inherit', 0)
        access = kwargs.get('access',
                            self.vm.remote.win32con.GENERIC_READ |
                            self.vm.remote.win32con.GENERIC_WRITE
                            )
        attr = self.vm.remote.win32security.SECURITY_ATTRIBUTES()
        attr.bInheritHandle = inherit

        desc = self.vm.remote.win32security.SECURITY_DESCRIPTOR()
        dacl = self.vm.remote.win32security.ACL()

        for sid in sids:
            dacl.AddAccessAllowedAce(
                self.vm.remote.win32security.ACL_REVISION_DS, access, sid
            )

        desc.SetSecurityDescriptorDacl(True, dacl, False)

        attr.SECURITY_DESCRIPTOR = desc
        return attr

    def _create_named_pipe(self, sids=None):
        """INTERNAL: create a named pipe."""
        if sids is None:
            sattrs = None
        else:
            sattrs = self._create_security_attributes(
                *sids,
                access=self.vm.remote.win32con.PROCESS_ALL_ACCESS
            )

        for i in range(100):
            name = PIPE_NAME.format(random.randint(0, 999999))
            try:
                # Try to create the named pipe
                pipe = self.vm.remote.win32pipe.CreateNamedPipe(
                    name,
                    self.vm.remote.win32con.PIPE_ACCESS_DUPLEX,
                    0, 1, 65536, 65536,
                    100000, sattrs

                )
                self.vm.remote.win32api.SetHandleInformation(
                    pipe,
                    self.vm.remote.win32con.HANDLE_FLAG_INHERIT,
                    0)

            except WindowsError, e:
                if e.winerror != self.vm.remote.winerror.ERROR_PIPE_BUSY:
                    # Pipe name is taken - try again with another name
                    raise
            else:
                return pipe, name

        raise Exception("Could not create pipe after 100 attempts.")

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

    def _create_startup_info(self, stdin_name,
                             stdout_name,
                             stderr_name,
                             daemon=False):

        startupinfo = self.vm.remote.win32process.STARTUPINFO()
        startupinfo.dwFlags |= self.vm.remote.win32con.STARTF_USESTDHANDLES | self.vm.remote.win32con.STARTF_USESHOWWINDOW
        startupinfo.lpDesktop = 'winsta0\default'

        if daemon:
            startupinfo.wShowWindow = self.vm.remote.win32con.SW_HIDE

        else:
            startupinfo.wShowWindow = self.vm.remote.win32con.SW_SHOWNORMAL

        # Get the named pipes
        stdin_pipe = self.vm.remote.win32file.CreateFile(stdin_name,
                                                         self.vm.remote.win32con.GENERIC_READ,
                                                         0, None,
                                                         self.vm.remote.win32con.OPEN_EXISTING,
                                                         0, None)

        # Make sure the pipe handles are inherited
        self.vm.remote.win32api.SetHandleInformation(stdin_pipe,
                                                     self.vm.remote.win32con.HANDLE_FLAG_INHERIT,
                                                     1)
        stdout_pipe = self.vm.remote.win32file.CreateFile(stdout_name,
                                                          self.vm.remote.win32con.GENERIC_WRITE,
                                                          0, None,
                                                          self.vm.remote.win32con.OPEN_EXISTING,
                                                          0, None)
        # Make sure the pipe handles are inherited
        self.vm.remote.win32api.SetHandleInformation(stdout_pipe,
                                                     self.vm.remote.win32con.HANDLE_FLAG_INHERIT,
                                                     1)
        stderr_pipe = self.vm.remote.win32file.CreateFile(stderr_name,
                                                          self.vm.remote.win32con.GENERIC_WRITE,
                                                          0, None,
                                                          self.vm.remote.win32con.OPEN_EXISTING,
                                                          0, None)
        # Make sure the pipe handles are inherited
        self.vm.remote.win32api.SetHandleInformation(stderr_pipe,
                                                     self.vm.remote.win32con.HANDLE_FLAG_INHERIT,
                                                     1)
        # Set the process's std pipes
        startupinfo.hStdInput = stdin_pipe
        startupinfo.hStdOutput = stdout_pipe
        startupinfo.hStdError = stderr_pipe

        return startupinfo

    def _pipe_chunk_reader(self, handle, chunk_size=2048):
        """INTERNAL: Reader thread that reads stdout/stderr of the child
        process."""
        status = 'data'
        while True:
            try:
                # TODO: Read File is stuck if process is complete or if no data is available. Handle this.
                err, data = self.vm.remote.win32file.ReadFile(handle, chunk_size)
                assert err == 0  # not expecting error w/o overlapped io
            except WindowsError, e:
                if e.winerror == self.vm.remote.winerror.ERROR_BROKEN_PIPE:
                    status = 'eof'
                    data = ''
                else:
                    status = 'error'
                    data = e.winerror
            return data, status

    def read(self, handle):
        data = ""
        chunk, status = self._pipe_chunk_reader(handle)
        while status == 'data':
            data += chunk
            chunk, status = self._pipe_chunk_reader(handle)

        return data


class UnixProcessPlugin(plugin.Plugin):
    """
    Process operations on Unix based vms.
    """
    _name = "process"
    _os = [plugin.UNIX]

    _PIDOF_COMMAND = "pidof"
    _KILLALL_COMMAND = "killall {name}"
    _RUN_COMMAND_AS_ADMIN_FORMAT = "echo {password} | sudo -S {command}"
    SIGKILL = 9

    def run(self, command, async=False, as_admin=False, daemon=True, shell=False):
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
        @rtype: I{Popen}
        """
        # Rewrite the command using sudo and the password
        if as_admin:
            self._RUN_COMMAND_AS_ADMIN_FORMAT.format(password=self.vm.password, command=command)
            # Needed to run as root
            shell = True

        # Run the process on the vm
        # TODO: close_fds might cause problems
        new_process = self.vm.remote.subprocess.Popen(command, shell=shell, close_fds=daemon)

        # Wait for the process to terminate.
        if not async:
            new_process.wait()

        return new_process

    def kill_process(self, process):
        """
        Kill a process.
        @param process: The process id or name.
        @type pid: int or stings
        """
        # If process is a name, get the process pids by name.
        if type(process) == str:
            processes_to_terminate = self.get_process_pids(process)
        else:
            # Insert pid to list
            processes_to_terminate = [process]

        # Kill each pid
        for pid in processes_to_terminate:
            self.signal_process(pid, self.SIGKILL)

    def get_process_pids(self, name):
        """
        Retrieve all process ids associated with a process name.
        @param name: The name of the process.
        @type name: str
        @return: The process pids
        @rtype: I{list}
        """
        # Get the pids of the process
        pids = self.vm.remote.subprocess.check_output((self._PIDOF_COMMAND, name)).split()
        return map(int, pids)

    def get_process_by_name(self, name):
        """

        @param name:
        @return:
        """
        # TODO: Find out how to do that
        raise NotImplementedError

    def get_process_by_id(self, pid):
        """

        @param ps:
        @return:
        """
        # TODO: Find out how to do that
        raise NotImplementedError

    def signal_process(self, pid, signal):
        """
        Send a signal to a process.
        @param pid: The id of the process to signal.
        @type pid: int
        @param signal: The signal number to send.
        @type: int
        """
        self.vm.remote.os.kill(pid, signal)