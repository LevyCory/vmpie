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
BUFFER_SIZE = 4096
PIPE_NAME = r'\\.\pipe\vmpie-{}'
PS_COMMAND = '$objUser = New-Object System.Security.Principal.NTAccount("{}", "{}"); $strSID = $objUser.Translate([System.Security.Principal.SecurityIdentifier]); return $strSID.Value'

# ===================================================== CLASSES ====================================================== #


def run_command(command, username=None, password=None, domain=None, daemon=False, as_admin=False):
    import pywintypes
    import subprocess
    import win32api
    import win32security
    import win32con
    import win32process
    import win32file
    import win32pipe
    import win32profile
    import win32event
    import winerror
    import random
    import ctypes
    import re

    PIPE_NAME = r'\\.\pipe\vmpie-{}'
    BUFFER_SIZE = 4096

    class WinProcess(object):
        def __init__(self, pid, process_handle, stdin_pipe, stdout_pipe, stderr_pipe):
            self.pid = pid
            self._process_handle = process_handle
            self._stdin_pipe = stdin_pipe
            self._stdout_pipe = stdout_pipe
            self._stderr_pipe = stderr_pipe
            self._stdout_eof = False
            self._stderr_eof = False

        @property
        def returncode(self):
            """
            The return code of the process (None if process is still running)
            :return: {int} The return code
            """
            returncode = win32process.GetExitCodeProcess(
                self._process_handle)

            if returncode != 259:
                # 259 returncode is STILL_ACTIVE
                return returncode

        def wait(self, timeout=None):
            """
            Wait for process and return its return code
            :param process_handle: {PyHANDLE} The process handle
            :return: {int} The return code of the process
            """
            if not timeout:
                timeout = win32event.INFINITE

            # Wait for the process to complete
            win32event.WaitForSingleObject(self._process_handle, timeout)

            # Get return code
            return win32process.GetExitCodeProcess(self._process_handle)

        def kill(self):
            """
            Kill the process
            """
            proc = win32api.OpenProcess(
                win32con.PROCESS_ALL_ACCESS,
                False,
                self.pid)
            # Kill process
            win32process.TerminateProcess(proc, 0)

            self._process_handle.close()
            self._stdin_pipe.close()
            self._stdout_pipe.close()
            self._stderr_pipe.close()


        def write(self, data, newline=True):
            """
            Write data to stdin
            :param data: {str} The data to write to the stdin
            :param newline: {bool} Whether to add newline (\n) after the data
            """
            win32file.WriteFile(self._stdin_pipe, data)
            if newline:
                win32file.WriteFile(self._stdin_pipe, "\n")

        def is_process_running(self):
            return win32event.WaitForSingleObject(
                self._process_handle, 0) != 0

        def read_stderr(self, chunk=BUFFER_SIZE):
            """
            Read output from stderr pipe (wait until EOF)
            :param chunk: {int} The size of the chunk to read each time
            :return: {str} The output
            """
            output = ""

            try:
                while True:
                    # Read from stdout
                    output += win32file.ReadFile(self._stderr_pipe, chunk)[1]
            except pywintypes.error as e:
                if e.winerror == winerror.ERROR_BROKEN_PIPE:
                    # Pipe is closed - no more data to read from the pipe
                    pass
                else:
                    raise

            self._stderr_pipe.Close()
            return output

        def read_stdout(self, chunk=BUFFER_SIZE):
            """
            Read output from std pipe
            :param std_pipe: {PyHANDLE} THe pipe handle
            :return: {str} The output
            """
            output = ""

            try:
                while True:
                    # Read from stdout
                    output += \
                    win32file.ReadFile(self._stdout_pipe, BUFFER_SIZE)[1]
            except pywintypes.error as e:
                if e.winerror == winerror.ERROR_BROKEN_PIPE:
                    # Pipe is closed - no more data to read from the pipe
                    pass
                else:
                    raise

            self._stdout_pipe.Close()
            return output

        def __del__(self):
            self._process_handle.close()
            self._stdin_pipe.close()
            self._stdout_pipe.close()
            self._stderr_pipe.close()


    class WinProcessManager(object):
        """
        Runners Manager
        """

        def __init__(self):
            pass

        def create_named_pipe(self, sids=None):
            """
            Create a named pipe.
            :param sids: {list} The sids to grant access to the pipe
            :return: {tuple} (The pipe, the name of the pipe)
            """
            if sids is None:
                sattrs = None
            else:
                # Create the security attributes of the pipe
                sattrs = self.create_security_attributes(
                    sids,
                    access=win32con.PROCESS_ALL_ACCESS
                )

            # Try to create a named pipe (find a free name)
            for i in range(100):
                name = PIPE_NAME.format(random.randint(0, 999999))
                try:
                    # Try to create the named pipe
                    pipe = win32pipe.CreateNamedPipe(
                        name,
                        win32con.PIPE_ACCESS_DUPLEX,
                        0, 1, 65536, 65536,
                        100000, sattrs

                    )

                    # Set the inheritance info of the pipe
                    win32api.SetHandleInformation(
                        pipe,
                        win32con.HANDLE_FLAG_INHERIT,
                        0)

                except WindowsError, e:
                    if e.winerror != winerror.ERROR_PIPE_BUSY:
                        # Pipe name is taken - try again with another name
                        raise
                else:
                    return pipe, name

            raise Exception("Could not create pipe after 100 attempts.")

        def create_security_attributes(self, sids, inherit=False,
                                       access=win32con.GENERIC_READ |
                                              win32con.GENERIC_WRITE):
            """
            Create a SECURITY_ATTRIBUTES structure.
            :param sids: {list} The sids to grant access to in the security attributes
            :param inherit: {bool} Whether to inherit handles or not
            :param access: {int} The access to grant
            :return: {SECURITY_ATTRIBUTES} The security attributes
            """

            attr = win32security.SECURITY_ATTRIBUTES()
            attr.bInheritHandle = inherit

            desc = win32security.SECURITY_DESCRIPTOR()
            dacl = win32security.ACL()

            for sid in sids:
                dacl.AddAccessAllowedAce(
                    win32security.ACL_REVISION_DS, access, sid
                )

            desc.SetSecurityDescriptorDacl(True, dacl, False)

            attr.SECURITY_DESCRIPTOR = desc
            return attr

        def lookup_sid(self, domain, username):
            """
            Get the sid of a user by domain and username
            :param domain: {str} The domain
            :param username: {str} The username
            :return: {PySID} The sid
            """
            try:
                return win32security.LookupAccountName(domain, username)[0]
            except Exception:
                try:
                    p = subprocess.Popen(
                        ["powershell", '-NoProfile', '-Command',
                         PS_COMMAND.format(domain, username)],
                        stdout=subprocess.PIPE)
                    return win32security.ConvertStringSidToSid(
                        p.communicate()[0].strip("\r\n"))
                except Exception:
                    raise Exception(
                        "Unable to get SID of {}\\{}".format(domain, username))

        def create_startup_info(self, stdin_name,
                                stdout_name,
                                stderr_name,
                                daemon=False):
            """
            Create the startup info for a process
            :param stdin_name: {str} The name of the stdin pipe
            :param stdout_name: {str} The name of the stdout pipe
            :param stderr_name: {str} The name of the stderr pipe
            :param daemon: {bool} Thether to run in the background or not
            :return: {STARTUPINFO} The startup info
            """
            startupinfo = win32process.STARTUPINFO()
            startupinfo.dwFlags |= win32con.STARTF_USESTDHANDLES | win32con.STARTF_USESHOWWINDOW

            if daemon:
                # Hide the window
                startupinfo.wShowWindow = win32con.SW_HIDE

            else:
                # Show the window
                startupinfo.wShowWindow = win32con.SW_SHOWNORMAL

            # Get the named pipes
            stdin_pipe = win32file.CreateFile(stdin_name,
                                              win32con.GENERIC_READ,
                                              0, None,
                                              win32con.OPEN_EXISTING,
                                              0, None)

            # Make sure the pipe handles are inherited
            win32api.SetHandleInformation(stdin_pipe,
                                          win32con.HANDLE_FLAG_INHERIT,
                                          1)
            stdout_pipe = win32file.CreateFile(stdout_name,
                                               win32con.GENERIC_WRITE,
                                               0, None,
                                               win32con.OPEN_EXISTING,
                                               0, None)
            # Make sure the pipe handles are inherited
            win32api.SetHandleInformation(stdout_pipe,
                                          win32con.HANDLE_FLAG_INHERIT,
                                          1)
            stderr_pipe = win32file.CreateFile(stderr_name,
                                               win32con.GENERIC_WRITE,
                                               0, None,
                                               win32con.OPEN_EXISTING,
                                               0, None)
            # Make sure the pipe handles are inherited
            win32api.SetHandleInformation(stderr_pipe,
                                          win32con.HANDLE_FLAG_INHERIT,
                                          1)
            # Set the process's std pipes
            startupinfo.hStdInput = stdin_pipe
            startupinfo.hStdOutput = stdout_pipe
            startupinfo.hStdError = stderr_pipe

            return startupinfo

        def get_current_sid(self):
            """
            Get the current process's / thread's sid
            :return: {PySID} The sid
            """
            try:
                # Try to get the token of the current thread
                token = win32security.OpenThreadToken(
                    win32api.GetCurrentThread(),
                    win32con.MAXIMUM_ALLOWED, True)
            except:
                # Try to get the token of the current process
                token = win32security.OpenProcessToken(
                    win32api.GetCurrentProcess(),
                    win32con.MAXIMUM_ALLOWED)

            # Get the sid by token
            return win32security.GetTokenInformation(
                token,
                win32security.TokenUser
            )[0]

        def get_user_token(self, ps='explorer.exe'):
            return self.__get_logged_on_user_token(
                tokenAccess=win32security.TOKEN_QUERY |
                            win32security.TOKEN_DUPLICATE |
                            win32security.TOKEN_ASSIGN_PRIMARY,
                ps=ps
            )

        def is_admin(self):
            try:
                return ctypes.windll.shell32.IsUserAnAdmin()
            except:
                return False

        def run_command_as_user(self, command, username, password, domain,
                                deamon=False, as_admin=False):
            """
            Run a command as another user
            :param command: {str} The command to run
            :param username: {str} The username
            :param password: {str} The password
            :param domain: {str} The domain
            :param as_admin: {bool} Whether to run as admin.
                If this is set to True, then the username, domain & password
                are ignored and the process will be ran as the owner of
                winlogon.exe process.
            :param deamon: {bool} Whether to run in the background or not
            :return:  {int, PyHANDLE, PyHANDLE, PyHANDLE, PyHANDLE} pid, process_handle, stdin_pipe, stdout_pipe, stderr_pipe
            """
            if as_admin and not self.is_admin():
                # Get the user token from the winlogon.exe process
                usertoken = self.get_user_token(ps='winlogon.exe')

            elif not (username or password or domain):
                # Run as currently logged on user
                usertoken = self.get_user_token(ps='explorer.exe')

            else:
                # Get token of given user
                usertoken = win32security.LogonUser(
                    username, domain, password,
                    win32con.LOGON32_LOGON_INTERACTIVE,
                    win32con.LOGON32_PROVIDER_DEFAULT,
                )

            # Get user's token
            usertoken = win32security.LogonUser(
                username, domain, password,
                win32con.LOGON32_LOGON_INTERACTIVE,
                win32con.LOGON32_PROVIDER_DEFAULT,
            )

            # Get the sid's of the current user and the given user to run the process as
            sids = [self.get_current_sid(), self.lookup_sid(domain, username)]

            # Create security attributes
            if sids is None:
                sattrs = None
            else:
                sattrs = self.create_security_attributes(
                    sids,
                    inherit=True,
                    access=win32con.PROCESS_ALL_ACCESS
                )

            # Create the named pipes
            stdin_pipe, stdin_name = self.create_named_pipe(sids)
            stdout_pipe, stdout_name = self.create_named_pipe(sids)
            stderr_pipe, stderr_name = self.create_named_pipe(sids)

            # Make sure that the parent process's pipe ends are not inherited
            win32api.SetHandleInformation(stdin_pipe,
                                          win32con.HANDLE_FLAG_INHERIT,
                                          0)
            win32api.SetHandleInformation(stdout_pipe,
                                          win32con.HANDLE_FLAG_INHERIT,
                                          0)
            win32api.SetHandleInformation(stderr_pipe,
                                          win32con.HANDLE_FLAG_INHERIT,
                                          0)

            try:
                environment = win32profile.CreateEnvironmentBlock(usertoken,
                                                                  False)
            except:
                environment = None

            try:
                profile_dir = win32profile.GetUserProfileDirectory(usertoken)
            except:
                profile_dir = None

            # Create process's startup info
            startup_info = self.create_startup_info(stdin_name,
                                                    stdout_name,
                                                    stderr_name,
                                                    deamon
                                                    )

            # Create process
            res = win32process.CreateProcessAsUser(
                usertoken, None, command, sattrs, None, True,
                win32con.CREATE_NEW_CONSOLE,
                environment, profile_dir,
                startup_info)

            process_handle = res[0]  # The process handle
            res[1].Close()  # Close the thread handle - not relevant
            pid = res[2]  # The pid

            # Connect to the pipes
            win32pipe.ConnectNamedPipe(stdin_pipe)
            win32pipe.ConnectNamedPipe(stdout_pipe)
            win32pipe.ConnectNamedPipe(stderr_pipe)

            return pid, process_handle, stdin_pipe, stdout_pipe, stderr_pipe

        def wait_for_process(self, process_handle):
            """
            Wait fir process and return its return code
            :param process_handle: {PyHANDLE} The process handle
            :return: {int} The return code of the process
            """
            # Wait for the process to complete
            win32event.WaitForSingleObject(process_handle, win32event.INFINITE)

            # Get return code
            return win32process.GetExitCodeProcess(process_handle)

        def read_stdout(self, std_pipe):
            """
            Read output from std pipe
            :param std_pipe: {PyHANDLE} THe pipe handle
            :return: {str} The output
            """
            output = ""

            try:
                while True:
                    # Read from stdout
                    output += win32file.ReadFile(std_pipe, BUFFER_SIZE)[1]
            except pywintypes.error as e:
                if e.winerror == winerror.ERROR_BROKEN_PIPE:
                    # Pipe is closed - no more data to read from the pipe
                    pass
                else:
                    raise

            std_pipe.Close()
            return output

        @staticmethod
        def parse_wmic_output(text):
            """
            Parse wmic output
            :param text: {str} The cmd wmic output
            :return: {list} The parsed output
            """
            result = []
            # remove empty lines
            lines = [s for s in text.splitlines() if s.strip()]
            # No Instance(s) Available
            if len(lines) == 0:
                return result
            header_line = lines[0]
            # Find headers and their positions
            headers = re.findall('\S+\s+|\S$', header_line)
            pos = [0]
            for header in headers:
                pos.append(pos[-1] + len(header))
            for i in range(len(headers)):
                headers[i] = headers[i].strip()
            # Parse each entries
            for r in range(1, len(lines)):
                row = {}
                for i in range(len(pos) - 1):
                    row[headers[i]] = lines[r][pos[i]:pos[i + 1]].strip()
                result.append(row)
            return result

    process_manager = WinProcessManager()
    pid, process_handle, stdin_pipe, stdout_pipe, stderr_pipe = process_manager.run_command_as_user(command, username, password, domain, daemon, as_admin)

    return WinProcess(pid, process_handle, stdin_pipe, stdout_pipe, stderr_pipe)


class WindowsProcessPlugin(plugin.Plugin):
    """
    Process operations on Windows virtual machines.
    """
    _name = "process"
    _os = [plugin.WINDOWS]


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

    def run(self, command, username=None, password=None,
                    domain=None, daemon=False, as_admin=False):
        """
        Run a command as another user
        :param command: {str} The command to run
        :param username: {str} The username to run as (optional)
        :param domain: {str} The domain of the user
        :param password: {str} The password of the user
        :param daemon: {bool} Whether to run in the background or not
        :param as_admin: {bool} Whether to run as admin.
            If this is set to True, then the username, domain & password
            are ignored and the process will be ran as the owner of
             winlogon.exe process.
        :return:  {int, PyHANDLE, PyHANDLE, PyHANDLE, PyHANDLE} pid, process_handle, stdin_pipe, stdout_pipe, stderr_pipe
        """
        remote_run_command = self.vm.remote.teleport(run_command)
        return remote_run_command(command, username, password, domain, daemon)


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
