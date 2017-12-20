# ==================================================================================================================== #
# File Name     : remote.py
# Purpose       : Provide a convenient way to perform RPC operations on virtual machines.
# Date Created  : 12/11/2017
# Author        : Avital Livshits, Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #

import sys
import uuid
import types
import inspect
import pickle
import Pyro4
import vmpie.consts as consts
import vmpie.plugin as plugin


# ==================================================== CONSTANTS ===================================================== #

TAB = "    "
FILE_CLOSED_STATE = "Closed"
FILE_OPEN_STATE = "Open"
REMOTE_OBJECT_CACHE_NAME = "_remote_object_cache_{uuid}".format(uuid=uuid.uuid4().get_hex())
_BUILTIN_TYPES = [
    type, object, bool, complex, dict, float, int, list, slice, str, tuple, set,
    frozenset, Exception, type(None), types.BuiltinFunctionType, types.GeneratorType,
    types.ModuleType, types.FunctionType, basestring, unicode, long, xrange, type(iter(xrange(10))), file,
    types.InstanceType, types.ClassType, types.DictProxyType
]

_LOCAL_OBJECT_ATTRS = frozenset([
    '_RemoteObject__oid', 'vm', '_RemoteObject__class_name', '_RemoteObject__module_name', '_RemoteObject__methods', '__class__', '__cmp__', '__del__', '__delattr__',
    '__dir__', '__doc__', '__getattr__', '__getattribute_', '__hash__',
    '__init__', '__metaclass__', '__module__', '__new__', '__reduce__',
    '__reduce_ex__', '__repr__', '__setattr__', '__slots__', '__str__',
    '__weakref__', '__dic__', '__members__', '__methods__',
])

VALUE_LABEL = 1
ITERABLE_LABEL = 2
REF_LABEL = 3
FILE_LABEL = 4

EXCLUDED_ATTRS = frozenset([
    '__class__', '__cmp__', '__del__', '__delattr__',
    '__dir__', '__doc__', '__getattr__', '__getattribute_', '__hash__',
    '__init__', '__metaclass__', '__module__', '__new__', '__reduce__',
    '__reduce_ex__', '__repr__', '__setattr__', '__slots__', '__str__',
    '__weakref__', '__dic__', '__members__', '__methods__',
])

# ==================================================== FUNCTIONS ===================================================== #


def remove_indentations(code):
    """
    Lower code indentation level.
    @param code: The code to lower its indentation level
    @return: The same code with less indentations
    @rtype: string
    """
    lines = code.splitlines()

    # Figure out how indented the code is
    indentation_level = lines[0].count(TAB) * 4

    # Remove preceding indentation from every line.
    for index, line in enumerate(lines):
        lines[index] = line[indentation_level:]

    return "\n".join(lines)


def inspect_methods(remote_object_cache_name, exculded_methods, oid):
    import inspect
    local_object = eval("{remote_object_cache_name}[{oid}]".format(
        remote_object_cache_name=remote_object_cache_name,
        oid=oid))
    methods = []

    for attr in dir(local_object):
        method = getattr(local_object, attr)
        if attr not in exculded_methods and inspect.ismethod(method):
            methods.append((attr, method.__doc__))
    return methods


def handle_unserializable_types(vm, remote_obj_name):
    oid = vm._pyro_daemon.evaluate("id({remote_obj_name})".format(
        remote_obj_name=remote_obj_name
    ))

    vm._pyro_daemon.execute("{remote_object_cache_name}[{oid}]={remote_obj_name}".format(
        remote_object_cache_name=REMOTE_OBJECT_CACHE_NAME,
        oid=oid,
        remote_obj_name=remote_obj_name)
    )

    return _RemoteObject(oid=oid, vm=vm)


def unpack(vm, object):
    label, data = object
    if label == VALUE_LABEL:
        return data
    elif label == ITERABLE_LABEL:
        data_type = type(data)
        unpacked_iterable = [unpack(vm, item) for item in data]
        return data_type(unpacked_iterable)
    elif label == REF_LABEL or FILE_LABEL:
        oid, class_name, module_name, methods = data
        return _RemoteObject(oid=oid, vm=vm, class_name=class_name, module_name=module_name, methods=methods)


def pack(obj):
    # Pack each argument as a tuple(type[reg/ref], value[real value/(oid, class, module, ,methods))
    # Check if picklable or if stream (ie: file, stdout, etc), and handle  accordingly.
    # Check if maybe we can implement RemoteFunction, RemoteMethod and RemoteSubmodule here and send it
    # instead of defining it in vmpie.
    if not isinstance(obj, str) and is_iterable(obj):
        data_type = type(obj)
        unpacked_iterable = [pack(item) for item in obj]
        return ITERABLE_LABEL, data_type(unpacked_iterable)
    elif is_file(obj):
        return FILE_LABEL, obj._RemoteObject__oid
    elif type(obj) in _BUILTIN_TYPES:
        return VALUE_LABEL, obj
    elif isinstance(obj, _RemoteObject):
        return REF_LABEL, obj._RemoteObject__oid


def is_iterable(p_object):
    try:
        it = iter(p_object)
    except TypeError:
        return False
    return True


def is_file(p_object):
    return isinstance(p_object, file)


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
        self.vm._pyro_daemon.execute("import pickle")

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
        return Pyro4.Proxy("PYRO:Vmpie.Server@192.168.70.72:2808")

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
        return unpack(self.vm, self.vm._pyro_daemon.evaluate("[p[1] for p in pkgutil.iter_modules()]"))

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
            unpack(self.vm, self.vm._pyro_daemon.execute("import %s" % self._name))
            self._imported = True

        # Check if item is a sub-module
        if unpack(self.vm, self.vm._pyro_daemon.evaluate("inspect.ismodule(%s.%s)" % (self._name, item))):
            return _RemoteSubModule(".".join([self._name, item]), self.vm)

        # Check if item is a method
        elif unpack(self.vm, self.vm._pyro_daemon.evaluate("callable(%s.%s)" % (self._name, item))):
            return _RemoteMethod(".".join([self._name, item]), self.vm)

        # Item is a regular attribute - return its value
        return unpack(self.vm, self.vm._pyro_daemon.evaluate("%s.%s" % (self._name, item)))


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
        if unpack(self.vm, self.vm._pyro_daemon.evaluate("inspect.ismodule(%s.%s)" % (self._name, item))):
            return _RemoteSubModule(".".join([self._name, item]), self.vm)

        # Check if item is a method
        elif unpack(self.vm, self.vm._pyro_daemon.evaluate("inspect.isfunction(%s.%s)" % (self._name, item))):
            return _RemoteMethod(".".join([self._name, item]), self.vm)

        # Item is a regular attribute - return its value
        return unpack(self.vm, self.vm._pyro_daemon.evaluate("%s.%s" % (self._name, item)))


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
        args = [pack(arg) for arg in args]
        kwargs = {key: pack(value) for key, value in kwargs.iteritems()}
        return unpack(self.vm, self.vm._pyro_daemon.invokeModule(self._name, args, kwargs))


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
        self.vm._pyro_daemon.execute(remove_indentations(inspect.getsource(func)))

    def __call__(self, *args, **kwargs):
        """
        Executes and evaluates the remote function.
        @return: The result of the function.
        """
        args = [pack(arg) for arg in args]
        kwargs = {key: pack(value) for key, value in kwargs.iteritems()}
        return unpack(self.vm, self.vm._pyro_daemon.call(pack(self._function_name), args, kwargs))



class _RemoteObject(object):
    """
    Executes and evaluates the remote method.
    @return: The result of the method.
    """
    __slots__ = ["vm", "__weakref__", "__oid", "__class_name", "__module_name", "__methods"]

    def __init__(self, vm, oid, class_name, module_name, methods):
        self.__oid = oid
        self.vm = vm
        self.__class_name = class_name
        self.__module_name = module_name
        self.__methods = methods

    normalized_builtin_types = {}

    def __getattribute__(self, name):
        return object.__getattribute__(self, name)

    def __getattr__(self, name):
        return unpack(self.vm, self.vm._pyro_daemon.getattr(pack(self), name))

    def __delattr__(self, name):
        if name in _LOCAL_OBJECT_ATTRS:
            object.__delattr__(self, name)
        else:
            return unpack(self.vm, self.vm._pyro_daemon.delattr(pack(self), name))

    def __setattr__(self, name, value):
        if name in _LOCAL_OBJECT_ATTRS:
            object.__setattr__(self, name, value)
        else:
            return unpack(self.vm, self.vm._pyro_daemon.setattr(pack(self), name, pack(value)))

    def __dir__(self):
        return unpack(self.vm, self.vm._pyro_daemon.dir(pack(self)))

    def __str__(self):
        return unpack(self.vm, self.vm._pyro_daemon.str(pack(self)))

    def __repr__(self):
        import pdb; pdb.set_trace()
        return unpack(self.vm, self.vm._pyro_daemon.repr(pack(self)))

    # def __reduce_ex_(self, proto):
    #     return pickle.loads, (self.vm._pyro_daemon.evaluate("pickle.dumps({remote_object_cache_name}[{oid}])".format(
    #         remote_object_cache_name=REMOTE_OBJECT_CACHE_NAME,
    #         oid=self._RemoteObject__oid)), )

    @classmethod
    def _create_class_proxy(cls, oid, vm, class_name, module_name, methods):
        """
        creates a proxy for the given class
        """
        def make_method(name):
            def method(self, *args, **kwargs):
                args = [pack(arg) for arg in args]
                kwargs = {key: pack(value) for key, value in kwargs.iteritems()}
                return unpack(self.vm, self.vm._pyro_daemon.callattr(pack(self), name, args, kwargs))

            return method

        namespace = {'__slots__': ()}
        for name, doc in methods:
            namespace[name] = make_method(name)
            namespace[name].__doc__ = doc

        normalized_builtin_types = dict(((t.__name__, t.__module__), t) for t in _BUILTIN_TYPES)

        namespace["__module__"] = module_name
        if module_name in sys.modules and hasattr(sys.modules[module_name], class_name):
            namespace["__class__"] = getattr(sys.modules[module_name], class_name)
        elif (class_name, module_name) in normalized_builtin_types:
            namespace["__class__"] = normalized_builtin_types[class_name, module_name]
        else:
            namespace["__class__"] = None

        return type(class_name, (cls,), namespace)

    def __new__(cls, oid, vm, class_name, module_name, methods, *args, **kwargs):
        """
        creates an proxy instance referencing `obj`. (obj, *args, **kwargs) are
        passed to this class' __init__, so deriving classes can define an
        __init__ method of their own.
        note: _class_proxy_cache is unique per deriving class (each deriving
        class must hold its own cache)
        """
        theclass = cls._create_class_proxy(oid, vm, class_name, module_name, methods)
        ins = object.__new__(theclass)
        return ins


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
