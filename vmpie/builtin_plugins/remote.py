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


# ===================================================== CLASSES ====================================================== #


# TODO(Avital): Document
class RemotePlugin(plugin.Plugin):
    """
    Provide RPC operations to virtual machines.
    """
    _name = "remote"
    _os = [plugin.UNIX, plugin.WINDOWS]

    def __init__(self, vm):
        """
        """
        # TODO: Check why super fails
        # super(RemotePlugin, self).__init__(vm)

        # TODO: Remove when super works
        self.vm = vm
        self.vm._pyro_daemon = self.connect()
        self.vm._pyro_daemon.execute("import inspect")

        for module_name in self._get_modules():
            setattr(self, module_name, _RemoteModule(module_name, self.vm))

    def connect(self):
        """
        """
        Pyro4.config.SERIALIZER = consts.DEFAULT_SERIALIZER
        # TODO: Don't hardcode the URI
        return Pyro4.Proxy("PYRO:Pyro.Flame@192.168.70.71:2808")

    def execute(self, code):
        """
        Execute code in the target machine.
        @param code:
        @return:
        """
        return self.vm._pyro_daemon.execute(code)

    def evaluate(self, code):
        """
        Evaluate the value of an expression on the target machine.
        @param code:
        @return:
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


# TODO(Avital): Document
class _RemoteModule(object):
    """
    """
    def __init__(self, module_name, vm):
        self._name = module_name
        self.vm = vm
        self._imported = False

    def __getattr__(self, item):
        """
        """
        if not self._imported:
            self.vm._pyro_daemon.execute("import %s" % self._name)
            self._imported = True

        if self.vm._pyro_daemon.evaluate("inspect.ismodule(%s.%s)" % (self._name, item)):
            return _RemoteSubModule(".".join([self._name, item]), self.vm)

        elif self.vm._pyro_daemon.evaluate("callable(%s.%s)" % (self._name, item)):
            return _RemoteMethod(".".join([self._name, item]), self.vm)

        return self.vm._pyro_daemon.evaluate("%s.%s" % (self._name, item))


# TODO(Avital): Document
class _RemoteSubModule(object):
    """
    """
    def __init__(self, module_name, vm):
        self._name = module_name
        self.vm = vm

    def __getattr__(self, item):
        if self.vm._pyro_daemon.evaluate("inspect.ismodule(%s.%s)" % (self._name, item)):
            return _RemoteSubModule(".".join([self._name, item]), self.vm)

        elif self.vm._pyro_daemon.evaluate("inspect.isfunction(%s.%s)" % (self._name, item)):
            return _RemoteMethod(".".join([self._name, item]), self.vm)

        return self.vm._pyro_daemon.evaluate("%s.%s" % (self._name, item))


# TODO(Avital): Document
class _RemoteMethod(object):
    """
    """
    def __init__(self, function_name, vm):
        self._name = function_name
        self.vm = vm

    def __call__(self, *args, **kwargs):
        return self.vm._pyro_daemon.invokeModule(self._name, args, kwargs)
        # return self.vm._pyro_daemon.evaluate("%s()", %self.name)
        # Need to handle args too


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


# TODO(Cory): Document
# TODO(Cory): Finish implementation
class _RemoteFile(object):
    """
    Represents a file object on a remote machine. Acts exactly like Python's regular
    file objects.
    """
    def __init__(self, path, mode, _pyro_daemon):
        self.__daemon = _pyro_daemon
        self._name = "file_{id}".format(id=uuid.uuid4().get_hex())

        self.__daemon.execute("{name} = open('{path}', '{mode}')".format(name=self._name, path=path, mode=mode))

    def __enter__(self):
        """
        Enable the remote file act as a context manager.
        @return: I{vmpie.remote._RemoteFile}
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
        @return: True if closed, Flase otherwise
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

        @param sequence:
        @return:
        """
        return self.__daemon.execute("{name}.writelines({data})".format(name=self._name, data=str(sequence)))

    def read(self, size=None):
        """

        @return:
        """
        if size is None:
            size = ""

        return self.__daemon.evaluate("{name}.read({size})".format(name=self._name, size=size))

    def readlines(self, sequence):
        """

        @return:
        """
        return self.__daemon.evaluate("{name}.writelines({data})".format(name=self._name, data=str(sequence)))

    def flush(self):
        """
        """
        return self.__daemon.execute("{name}.flush()".format(name=self._name))

    def seek(self):
        pass

    def tell(self):
        pass

    def __str__(self):
        """
        """
        raise NotImplementedError

    def __repr__(self):
        """
        """
        raise NotImplementedError
