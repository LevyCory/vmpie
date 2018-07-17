# ==================================================================================================================== #
# File Name     : process.py
# Purpose       : Provides processing operations on virtual machines.
# Date Created  : 11/12/2017
# Author        : Avital Livshits, Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

import random
import vmpie.plugin as plugin

# ==================================================== CONSTANTS ===================================================== #

PARAM_INCORRECT_ERRNO = 87
WAIT_TIMEOUT = 258
BUFFER_SIZE = 4096
PIPE_NAME = r'\\.\pipe\vmpie-{}'
PS_COMMAND = '$objUser = New-Object System.Security.Principal.NTAccount("{}", "{}"); $strSID = $objUser.Translate([System.Security.Principal.SecurityIdentifier]); return $strSID.Value'

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

    def get_process_by_id(self, pid):
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

    def _get_current_sid(self):
        """
        Get the current process's / thread's sid
        :return: {PySID} The sid
        """
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
        """
        Get the sid of a user by domain and username
        :param domain: {str} The domain
        :param username: {str} The username
        :return: {PySID} The sid
        """
        try:
            return self.vm.remote.win32security.LookupAccountName(domain, username)[0]
        except Exception:
            try:
                p = self.vm.remote.subprocess.Popen(["powershell", '-NoProfile', '-Command',
                                      PS_COMMAND.format(domain, username)],
                                     stdout=self.vm.remote.subprocess.PIPE)
                return self.vm.remote.win32security.ConvertStringSidToSid(
                    p.communicate()[0].strip("\r\n"))
            except Exception:
                raise Exception("Unable to get SID of {}\\{}".format(domain, username))

    def _create_security_attributes(self, sids, inherit=False, access=None):
        """
        Create a SECURITY_ATTRIBUTES structure.
        :param sids: {list} The sids to grant access to in the security attributes
        :param inherit: {bool} Whether to inherit handles or not
        :param access: {int} The access to grant
        :return: {SECURITY_ATTRIBUTES} The security attributes
        """
        if not access:
            access = self.vm.remote.win32con.GENERIC_READ | self.vm.remote.win32con.win32con.GENERIC_WRITE

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
        """
        Create a named pipe.
        :param sids: {list} The sids to grant access to the pipe
        :return: {tuple} (The pipe, the name of the pipe)
        """
        if sids is None:
            sattrs = None
        else:
            sattrs = self._create_security_attributes(
                sids,
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

    def _create_startup_info(self, stdin_name,
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
        startupinfo = self.vm.remote.win32process.STARTUPINFO()
        startupinfo.dwFlags |= self.vm.remote.win32con.STARTF_USESTDHANDLES | self.vm.remote.win32con.STARTF_USESHOWWINDOW

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
        if as_admin and not self._is_admin():
            # Get the user token from the winlogon.exe process
            usertoken = self.__get_user_token(ps='winlogon.exe')

        elif not (username or password or domain):
            # Run as currently logged on user
            usertoken = self.__get_user_token(ps='explorer.exe')

        else:
            # Get token of given user
            usertoken = self.vm.remote.win32security.LogonUser(
                username, domain, password,
                self.vm.remote.win32con.LOGON32_LOGON_INTERACTIVE,
                self.vm.remote.win32con.LOGON32_PROVIDER_DEFAULT,
            )

        sids = [self._get_current_sid()]

        if username and password:
            # Get the sid of the given user
            sids.append(self._lookup_sid(domain, username))

        if sids is None:
            sattrs = None
        else:
            # Create the security attributes
            sattrs = self._create_security_attributes(
                sids,
                inherit=True,
                access=self.vm.remote.win32con.PROCESS_ALL_ACCESS
            )

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

        try:
            # Create environment for the usertoken
            environment = self.vm.remote.win32profile.CreateEnvironmentBlock(usertoken, False)
        except:
            environment = None

        try:
            # Get the user profile directory of the given user
            profile_dir = self.vm.remote.win32profile.GetUserProfileDirectory(usertoken)
        except:
            profile_dir = None

        # Create process's startup info
        startup_info = self._create_startup_info(stdin_name,
                                                 stdout_name,
                                                 stderr_name,
                                                 daemon
        )

        # Create the process
        res = self.vm.remote.win32process.CreateProcessAsUser(
            usertoken, None, command, sattrs, None, True,
            self.vm.remote.win32con.CREATE_NEW_CONSOLE,
            environment, profile_dir,
            startup_info)

        process_handle = res[0]  # The process handle
        res[1].Close()  # Close the thread handle - not relevant
        pid = res[2]  # The pid

        # Connect to the pipes
        self.vm.remote.win32pipe.ConnectNamedPipe(stdin_pipe)
        self.vm.remote.win32pipe.ConnectNamedPipe(stdout_pipe)
        self.vm.remote.win32pipe.ConnectNamedPipe(stderr_pipe)

        return WinProcess(self.vm, pid, process_handle, stdin_pipe, stdout_pipe, stderr_pipe)

    def kill_process(self, pid):
        """
        Kill a process by PID.
        @param pid: The process PID
        @type pid: I{int}
        """
        # Get process by pid
        proc = self.vm.remote.win32api.OpenProcess(self.vm.remote.win32con.PROCESS_ALL_ACCESS,
                                                   False,
                                                   pid)
        # Kill process
        self.vm.remote.win32process.TerminateProcess(proc, 0)


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

    def run(self, command, as_admin=False, daemon=True, shell=False):
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
        new_process = self.vm.remote.subprocess.Popen(command,
                                                      stdout=self.vm.remote.subprocess.PIPE,
                                                      stderr=self.vm.remote.subprocess.PIPE,
                                                      stdin=self.vm.remote.subprocess.PIPE,
                                                      shell=shell,
                                                      close_fds=daemon)

        return UnixProcess(self.vm, new_process)

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


class UnixProcess(object):
    def __init__(self, vm, popen):
        self.vm = vm
        self.popen = popen
        self._stdout = ""
        self._stderr = ""

    @property
    def returncode(self):
        """
        The return code of the process (None if process is still running)
        :return: {int} The return code
        """
        return self.popen.returncode

    @property
    def running(self):
        """
        Check if a process is still running
        :return: {bool} True if process is still running, False otherwise.
        """
        # Wait for the process to complete
        return self.popen.poll()

    def wait(self):
        self.popen.wait()
        return self.returncode

    def kill(self):
        self.vm.remote.os.kill(self.popen.pid, 9)

    def write(self, data, newline=True):
        self.popen.stdin.write(data)

        if newline:
            self.popen.stdin.write("\n")

    def read_stdout(self, chunk=BUFFER_SIZE):
        """
        Read output from stdout pipe (wait until EOF)
        :param chunk: {int} The size of the chunk to read each time
        :return: {str} The output
        """
        return self.popen.stdout.read()

    def read_stderr(self, chunk=BUFFER_SIZE):
        """
        Read output from stderr pipe (wait until EOF)
        :param chunk: {int} The size of the chunk to read each time
        :return: {str} The output
        """
        return self.popen.stderr.read()

    def read_stdout_nonblocking(self, chunk=BUFFER_SIZE):
        """
        Read output from stdout pipe (wait until EOF)
        :param chunk: {int} The size of the chunk to read each time
        :return: {str} The output
        """
        return self.popen.stdout.read(chunk)

    def read_stderr_nonblocking(self, chunk=BUFFER_SIZE):
        """
        Read output from stdout pipe (wait until EOF)
        :param chunk: {int} The size of the chunk to read each time
        :return: {str} The output
        """
        return self.popen.stderr.read(chunk)


class WinProcess(object):
    def __init__(self, vm, pid, process_handle, stdin_pipe, stdout_pipe, stderr_pipe):
        self.vm = vm
        self.pid = pid
        self._process_handle = process_handle
        self._stdin_pipe = stdin_pipe
        self._stdout_pipe = stdout_pipe
        self._stderr_pipe = stderr_pipe
        self._stdout_closed = False
        self._stderr_closed = False
        self._closed = False

    @property
    def returncode(self):
        """
        The return code of the process (None if process is still running)
        :return: {int} The return code
        """
        returncode = self.vm.remote.win32process.GetExitCodeProcess(
            self._process_handle)

        if returncode != 259:
            # 259 returncode is STILL_ACTIVE
            return returncode

    @property
    def running(self):
        """
        Check if a process is still running
        :return: {bool} True if process is still running, False otherwise.
        """
        if not self._closed:
            # Wait for the process to complete
            return self.vm.remote.win32event.WaitForSingleObject(
                self._process_handle, 0) == WAIT_TIMEOUT

        return True

    def wait(self):
        """
        Wait for process and return its return code
        :param process_handle: {PyHANDLE} The process handle
        :return: {int} The return code of the process
        """
        # Wait for the process to complete
        self.vm.remote.win32event.WaitForSingleObject(self._process_handle, self.vm.remote.win32event.INFINITE)

        # Get return code
        return self.vm.remote.win32process.GetExitCodeProcess(self._process_handle)

    def kill(self):
        """
        Kill the process
        """
        if self.running:
            proc = self.vm.remote.win32api.OpenProcess(
                self.vm.remote.win32con.PROCESS_ALL_ACCESS,
                False,
                self.pid)
            # Kill process
            self.vm.remote.win32process.TerminateProcess(proc, 0)

        self._process_handle.close()
        self._stdin_pipe.close()
        self._stdout_pipe.close()
        self._stderr_pipe.close()
        self._closed = True

    def write(self, data, newline=True):
        """
        Write data to stdin
        :param data: {str} The data to write to the stdin
        :param newline: {bool} Whether to add newline (\n) after the data
        """
        self.vm.remote.win32file.WriteFile(self._stdin_pipe, data)
        if newline:
            self.vm.remote.win32file.WriteFile(self._stdin_pipe, "\n")

    def read_stdout(self, chunk=BUFFER_SIZE):
        """
        Read output from stdout pipe (wait until EOF)
        :param chunk: {int} The size of the chunk to read each time
        :return: {str} The output
        """
        output = ""

        if self._stdout_closed:
            return output

        try:
            while True:
                if not self.running and not \
                        self.vm.remote.win32pipe.PeekNamedPipe(
                            self._stdout_pipe, chunk)[1]:
                    # Process is finished and no more data is available - break
                    # the loop

                    break

                # Process is still running or there is more data to read -
                # continue trying to read more data
                _, bytes_to_read, _ = self.vm.remote.win32pipe.PeekNamedPipe(
                    self._stdout_pipe, chunk)

                # Check whether there is data to read from the pipe
                if bytes_to_read:
                    output += \
                        self.vm.remote.win32file.ReadFile(self._stdout_pipe,
                                                          min(bytes_to_read,
                                                              chunk))[1]

        except self.vm.remote.pywintypes.error as e:
            if e.winerror == self.vm.remote.winerror.ERROR_BROKEN_PIPE:
                # Pipe is closed - no more data to read from the pipe
                pass
            else:
                raise

        self._stdout_pipe.close()
        self._stdout_closed = True
        return output

    def read_stderr(self, chunk=BUFFER_SIZE):
        """
        Read output from stderr pipe (wait until EOF)
        :param chunk: {int} The size of the chunk to read each time
        :return: {str} The output
        """
        output = ""

        if self._stderr_closed:
            raise EOFError("Pipe is closed. No more data to read from pipe.")

        try:
            while True:
                if not self.running and not \
                        self.vm.remote.win32pipe.PeekNamedPipe(
                            self._stderr_pipe, chunk)[1]:
                    # Process is finished and no more data is available - break
                    #  loop

                    break

                # Process is still running or there is more data to read -
                # continue trying to read more data
                _, bytes_to_read, _ = self.vm.remote.win32pipe.PeekNamedPipe(
                    self._stderr_pipe, chunk)

                # Check whether there is data to read from the pipe
                if bytes_to_read:
                    output += \
                        self.vm.remote.win32file.ReadFile(self._stderr_pipe,
                                                          min(bytes_to_read,
                                                              chunk))[1]

        except self.vm.remote.pywintypes.error as e:
            if e.winerror == self.vm.remote.winerror.ERROR_BROKEN_PIPE:
                # Pipe is closed - no more data to read from the pipe
                pass
            else:
                raise

        self._stderr_pipe.close()
        self._stderr_closed = True
        return output

    def read_stdout_nonblocking(self, chunk=BUFFER_SIZE):
        """
        Read output from stdout pipe non blocking (read only the
        currently available data)
        :param chunk: {int} The size of the chunk to read
        :return: {str} The output
        """
        if self._stdout_closed:
            return ""

        try:
            # Read from stdout
            _, bytes_to_read, _ = self.vm.remote.win32pipe.PeekNamedPipe(
                self._stdout_pipe, 0)

            if bytes_to_read:
                return self.vm.remote.win32file.ReadFile(self._stdout_pipe,
                                                         min(bytes_to_read,
                                                             chunk))[1]
            elif not self.running:
                self._stdout_closed = True

        except self.vm.remote.pywintypes.error as e:
            if e.winerror == self.vm.remote.winerror.ERROR_BROKEN_PIPE:
                # Pipe is closed - no more data to read from the pipe
                self._stdout_closed = True
                self._stdout_pipe.close()
            else:
                raise

        return ""

    def read_stderr_nonblocking(self, chunk=BUFFER_SIZE):
        """
        Read output from stderr pipe non blocking (read only the
        currently available data)
        :param chunk: {int} The size of the chunk to read
        :return: {str} The output
        """
        if self._stderr_closed:
            return ""

        try:
            # Read from stdout
            _, bytes_to_read, _ = self.vm.remote.win32pipe.PeekNamedPipe(
                self._stderr_pipe, 0)

            if bytes_to_read:
                return self.vm.remote.win32file.ReadFile(self._stderr_pipe,
                                                         min(bytes_to_read,
                                                             chunk))[1]
            elif not self.running:
                self._stdout_closed = True

        except self.vm.remote.pywintypes.error as e:
            if e.winerror == self.vm.remote.winerror.ERROR_BROKEN_PIPE:
                # Pipe is closed - no more data to read from the pipe
                self._stderr_closed = True
                self._stderr_pipe.close()
            else:
                raise

        return ""

    def __del__(self):
        self._process_handle.close()
        self._stdin_pipe.close()
        self._stdout_pipe.close()
        self._stderr_pipe.close()