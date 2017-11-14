# ==================================================================================================================== #
# File Name     : remote.py
# Purpose       : Provide a convenient way to perform RPC operations on virtual machines.
# Date Created  : 12/11/2017
# Author        : Avital Livshits, Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

import uuid
import inspect
import Pyro4

import vmpie.consts as consts
import vmpie.plugin as plugin


# ==================================================== CONSTANTS ===================================================== #

FILE_CLOSED_STATE = "Closed"
FILE_OPEN_STATE = "Open"

# ===================================================== CLASSES ====================================================== #


class RemotePlugin(plugin.Plugin):
    """
    Provide RPC operations to virtual machines.
    """
    _name = "remote"
    _os = [plugin.UNIX, plugin.WINDOWS]

    def __init__(self, vm):
        """
        Creates a remote plugin object and injects all the python importable modules on
        the target machine to the object.
        @param vm: The target machine
        @type vm: vmpie.virtual_machine.VirtualMachine
        """
        super(RemotePlugin, self).__init__(vm)

        self.vm._pyro_daemon = self.connect()
        self.vm._pyro_daemon.execute("import inspect")

        # Get all the python importable modules on the target machine and inject them to as attributes.
        for module_name in self._get_modules():
            setattr(self, module_name, _RemoteModule(module_name, self.vm))

    def connect(self):
        """
        Connects to the Pyro server on the target machine.
        @return: Pyro4 proxy to the Pyro server on the target machine.
        @rtype: Pyro4.Proxy
        """
        Pyro4.config.SERIALIZER = consts.DEFAULT_SERIALIZER
        # TODO: Don't hardcode the URI
        return Pyro4.Proxy("PYRO:Pyro.Flame@192.168.70.71:2808")

    def execute(self, code):
        """
        Execute code in the target machine.
        @param code: The code to execute in the target machine.
        @type code: str
        """
        self.vm._pyro_daemon.execute(code)

    def evaluate(self, code):
        """
        Evaluate the value of an expression on the target machine.
        @param code: The code to evaluate in the target machine.
        @type code: str
        @return: The returned value of the expression
        """
        return self.vm._pyro_daemon.evaluate(code)

    def _get_modules(self):
        """
        """
        self.vm._pyro_daemon.execute("import pkgutil")
        return self.vm._pyro_daemon.evaluate("[p[1] for p in pkgutil.iter_modules()]")

    def teleport(self, func):
        """
        Teleport a locally defined function to the target machine.
        @param func: The function to teleport to the target machine.
        @return: A matching remote callable function.
        @rtype: RemoteFunction
        """
        return _RemoteFunction(func, self.vm)


class _RemoteModule(object):
    """
    Represents a remote module on the target machine.
    """
    def __init__(self, module_name, vm):
        """
        Creates a remote module object.
        @param module_name: The name of the remote module on the target machine.
        @type module_name: str
        @param vm: The target machine
        @type vm: vmpie.virtual_machine.VirtualMachine
        """
        self._name = module_name
        self.vm = vm
        self._imported = False

    def __getattr__(self, item):
        """
        Detects the type of the desired attribute (sub-module, method or attribute) and returns
        the corresponding object.
        @param item: The desired attribute
        @type item: str
        @return: The matching remote object or the value of the attribute.
        @rtype: RemoteSubModule / RemoteMethod / object (value of the attribute)
        """
        # Import the module of it hasn't been loaded yet (caching)
        if not self._imported:
            self.vm._pyro_daemon.execute("import %s" % self._name)
            self._imported = True

        # Check if item is a sub-module
        if self.vm._pyro_daemon.evaluate("inspect.ismodule(%s.%s)" % (self._name, item)):
            return _RemoteSubModule(".".join([self._name, item]), self.vm)

        # Check if item is a method
        elif self.vm._pyro_daemon.evaluate("callable(%s.%s)" % (self._name, item)):
            return _RemoteMethod(".".join([self._name, item]), self.vm)

        # Item is a regular attribute - return its value
        return self.vm._pyro_daemon.evaluate("%s.%s" % (self._name, item))


class _RemoteSubModule(object):
    """
    Represents a remote sub-module on the target machine.
    """
    def __init__(self, module_name, vm):
        """
        Creates a remote sub-module object (ie: os.path).
        @param module_name: The name of the remote sub-module on the target machine.
        @type module_name: str
        @param vm: The target machine
        @type vm: vmpie.virtual_machine.VirtualMachine
        """
        self._name = module_name
        self.vm = vm

    def __getattr__(self, item):
        """
        Detects the type of the desired attribute (sub-module, method or attribute) and returns
        the corresponding object.
        @param item: The desired attribute
        @type item: str
        @return: The matching remote object or the value of the attribute.
        @rtype: RemoteSubModule / RemoteMethod / object (value of the attribute)
        """
        # Check if item is a sub-module
        if self.vm._pyro_daemon.evaluate("inspect.ismodule(%s.%s)" % (self._name, item)):
            return _RemoteSubModule(".".join([self._name, item]), self.vm)

        # Check if item is a method
        elif self.vm._pyro_daemon.evaluate("inspect.isfunction(%s.%s)" % (self._name, item)):
            return _RemoteMethod(".".join([self._name, item]), self.vm)

        # Item is a regular attribute - return its value
        return self.vm._pyro_daemon.evaluate("%s.%s" % (self._name, item))


class _RemoteMethod(object):
    """
    Represents a remote method on the target machine.
    """
    def __init__(self, function_name, vm):
        """
        Create a remote callable method
        @param function_name: The name of the method.
        @type function_name: str
        @param vm: The target machine
        @type vm: vmpie.virtual_machine.VirtualMachine
        """
        self._name = function_name
        self.vm = vm

    def __call__(self, *args, **kwargs):
        """
        Executes and evaluates the remote method.
        @return: The result of the method.
        """
        return self.vm._pyro_daemon.invokeModule(self._name, args, kwargs)


class _RemoteFunction(object):
    """
    Represents a remote instance of a given function
    """
    def __init__(self, func, vm):
        """
        Given a local function, create a remote instance of the function in the target machine.
        @param func: The local function
        @type func: function
        @param vm: The target machine.
        @type vm: vmpie.virtual_machine.VirtualMachine
        """
        self.vm = vm
        self._function_name = func.__name__
        self.vm._pyro_daemon.execute(inspect.getsource(func))

    def __call__(self, *args, **kwargs):
        """
        Executes and evaluates the remote function.
        @return: The result of the function.
        """
        return self.vm._pyro_daemon.evaluate("{function_name}(*{args}, **{kwargs})"
                                             .format(function_name=self._function_name,
                                                     args=args,
                                                     kwargs=kwargs))


class _RemoteFile(object):
    """
    Represents a file object on a remote machine. Acts exactly like Python's regular
    file objects.
    """
    def __init__(self, path, mode, _pyro_daemon):
        self.__daemon = _pyro_daemon
        self._name = "file_{id}".format(id=uuid.uuid4().get_hex())
        self.name = path
        self.__daemon.execute("{name} = open('{path}', '{mode}')".format(name=self._name, path=path, mode=mode))

    def __enter__(self):
        """
        Enable the remote file act as a context manager.
        @return: I{vmpie.builtin_plugins.remote._RemoteFile}
        """
        return self

    def __exit__(self, *args):
        """
        Enable the remote file act as a context manager.
        """
        self.close()

    def close(self):
        """
        Close the remote file.
        """
        self.__daemon.execute("{name}.close()".format(name=self._name))

    @property
    def closed(self):
        """
        Return whether the file is closed or not.
        @return: True if closed, False otherwise
        @rtype: I{bool}
        """
        return self.__daemon.evaluate("{name}.closed".format(name=self._name))

    @property
    def encoding(self):
        """
        Return the encoding of the file.
        @return: Encoding of the remote file
        @rtype:
        """
        return self.__daemon.evaluate("{name}.encoding".format(name=self._name))

    def fileno(self):
        """
        Return the file descriptor for the file on the remote machine.
        @return: Remote file file-descriptor
        @rtype: I{int}
        """
        return self.__daemon.evaluate("{name}.fileno()".format(name=self._name))

    def write(self, data):
        """
        Write data to the remote file.
        @param data: The data to write
        @type data: I{str}
        """
        return self.__daemon.execute("{name}.write('{data}')".format(name=self._name, data=data))

    def writelines(self, sequence):
        """
        Write the strings to the file.
        @param sequence: The strings to write.
        @type sequence: I{sequence}
        @return:
        """
        return self.__daemon.execute("{name}.writelines({data})".format(name=self._name, data=str(sequence)))

    def read(self, size=-1):
        """
        Read I{size} bytes from the file. If I{size} is omitted, read until EOF.
        @return: The read data.
        @rtype: I{str}
        """
        return self.__daemon.evaluate("{name}.read({size})".format(name=self._name, size=size))

    def readline(self, size=-1):
        """
        Read a line from the file. If I{size} is given, read up to I{size} bytes.
        @param size: Bytes to read. Defaults to -1, e.g. read 1 line.
        @type size: I{int}
        @return: The read data.
        @rtype: I{str}
        """
        return self.__daemon.evaluate("{name}.readline({size})").format(name=self._name, size=size)

    def readlines(self, size):
        """
        Read the file as lines. If I{size} is given, read up to I{size} bytes.
        @param size: Bytes to read. Defaults to -1, e.g. read 1 line.
        @type size: I{int}
        @return: The read data.
        @rtype: I{str}
        """
        return self.__daemon.evaluate("{name}.readlines({size})").format(name=self._name, size=size)

    def flush(self):
        """
        Flush the machine's I/O buffer.
        """
        return self.__daemon.execute("{name}.flush()".format(name=self._name))

    def seek(self, offset, whence=0):
        """
        Move the file cursor I{offset} bytes forward.
        @param offset: Number of bytes to move the cursor by.
        @type offset: I{int}
        @param whence: Where to start the seek from. Defaults to the start of the file.
        @type whence: I{int}
        """
        self.__daemon.execute("{name}.seek({offset}, {whence})").format(name=self._name, offset=offset, whence=whence)

    def tell(self):
        """
        Return the current position of the file cursor.
        @return: Current position of the file cursor.
        @rtype: I{int}
        """
        return self.__daemon.execute("{name}.tell()".format(name=self._name))

    def __str__(self):
        # Determine the file's state
        state = FILE_CLOSED_STATE if self.closed else FILE_OPEN_STATE
        return "{state} _RemoteFile at {path}".format(state=state, path=self.name)

    def __repr__(self):
        # Determine the file's state
        state = FILE_CLOSED_STATE if self.closed else FILE_OPEN_STATE
        return "{state} _RemoteFile at {path}".format(state=state, path=self.name)
