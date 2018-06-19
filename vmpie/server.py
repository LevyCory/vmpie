# ==================================================================================================================== #
# File Name     : server.py
# Purpose       : The Remote Pyro Server
# Date Created  : 20/12/2017
# Author        : Avital Livshits, Cory Levy
# ==================================================================================================================== #
# ===================================================== IMPORTS ====================================================== #
from __future__ import print_function
import sys
import os
from collections import Mapping

os.environ["FLAME_ENABLED"] = "true"
os.environ["PYRO_FLAME_ENABLED"] = "true"
os.environ["PYRO_SERIALIZERS_ACCEPTED"] = '{"pickle"}'
os.environ["PYRO_SERIALIZER"] = "pickle"
import pickle
import types
from Pyro4.utils.flame import Flame
from Pyro4 import errors, core
import sys
from Pyro4.configuration import config
from Pyro4 import core
from Pyro4.utils import flame

# ==================================================== CONSTANTS ===================================================== #


SERVER_NAME = "Vmpie.Server"

VALUE_LABEL = 1
ITERABLE_LABEL = 2
REF_LABEL = 3
FILE_LABEL = 4
MAPPING_LABEL = 5
PICKLED_LABEL = 1

EXCLUDED_ATTRS = frozenset([
    '__class__', '__cmp__', '__del__', '__delattr__',
    '__dir__', '__doc__', '__getattr__', '__getattribute_', '__hash__',
    '__init__', '__metaclass__', '__module__', '__new__', '__reduce__',
    '__reduce_ex__', '__repr__', '__setattr__', '__slots__', '__str__',
    '__weakref__', '__dic__', '__members__', '__methods__',
])

_BUILTIN_TYPES = [
    type, object, bool, complex, dict, float, int, list, slice, str, tuple,
    set,
    frozenset, Exception, type(None), types.BuiltinFunctionType,
    types.GeneratorType,
    types.ModuleType, types.FunctionType, basestring, unicode, long, xrange,
    type(iter(xrange(10))), file,
    types.InstanceType, types.ClassType, types.DictProxyType
]


# ==================================================== FUNCTIONS ===================================================== #

def is_iterable(p_object):
    try:
        iter(p_object)
    except TypeError:
        return False
    return True


def is_file(p_object):
    return isinstance(p_object, file)


def inspect_methods(obj):
    import inspect
    methods = []
    for attr in dir(obj):
        method = getattr(obj, attr)
        if attr not in EXCLUDED_ATTRS and (
                inspect.ismethod(method) or inspect.isbuiltin(method)):
            methods.append((attr, method.__doc__))
    return methods


def start(daemon):
    """
    Create and register a Flame server in the given daemon.
    Be *very* cautious before starting this: it allows the clients full access to everything on your system.
    """
    if config.FLAME_ENABLED:
        if set(config.SERIALIZERS_ACCEPTED) != {"pickle"}:
            raise errors.SerializeError(
                "Flame requires the pickle serializer exclusively")
        return daemon.register(Server(), SERVER_NAME)
    else:
        raise errors.SecurityError(
            "Flame is disabled in the server configuration")


def connect(location, hmac_key=None):
    """
    Connect to a Flame server on the given location, for instance localhost:9999 or ./u:unixsock
    This is just a convenience function to creates an appropriate Pyro proxy.
    """
    if config.SERIALIZER != "pickle":
        raise errors.SerializeError("Flame requires the pickle serializer")
    proxy = core.Proxy("PYRO:%s@%s" % (SERVER_NAME, location))
    if hmac_key:
        proxy._pyroHmacKey = hmac_key
    proxy._pyroBind()
    return proxy


# ===================================================== CLASSES ====================================================== #
@core.expose
class Server(Flame):
    """
    The actual FLAME server logic.
    Usually created by using :py:meth:`core.Daemon.startFlame`.
    Be *very* cautious before starting this: it allows the clients full access to everything on your system.
    """

    def __init__(self):
        self.local_storage = {}
        super(Server, self).__init__()

    def unpack(self, object):
        label, data = object

        if label == VALUE_LABEL:
            return data
        elif label == ITERABLE_LABEL:
            data_type = type(data)
            unpacked_iterable = [self.unpack(item) for item in data]
            return data_type(unpacked_iterable)
        elif label == MAPPING_LABEL:
            for key, value in data.items():
                data[key] = self.unpack(value)
            return data
        elif label == REF_LABEL or FILE_LABEL:
            try:
                return self.local_storage[data]
            except KeyError:
                # TODO: Create custom exception with oid to catch in local client and notify with object doesn't exists
                raise

    # TODO: Add a function to check if packing is needed (for smarter packing)
    # TODO: Maybe we could just pass references to all objects? Why passing the objects at all?

    def pack(self, obj):
        """
        Pack each argument as a tuple(type[reg/ref], value[real value/(oid, class, module, ,methods))
        Check if picklable or if stream (ie: file, stdout, etc), and handle  accordingly.
        Check if maybe we can implement RemoteFunction, RemoteMethod and RemoteSubmodule here and send it
        instead of defining it in vmpie.
        """
        try:
            if is_file(obj):
                self.local_storage[id(obj)] = obj
                return FILE_LABEL, (
                id(obj), obj.__class__.__name__, obj.__class__.__module__,
                inspect_methods(obj))
            elif isinstance(obj, Mapping):
                for key, value in obj.items():
                    obj[key] = self.pack(value)
                return MAPPING_LABEL, obj
            elif not isinstance(obj, basestring) and is_iterable(obj):
                data_type = type(obj)
                unpacked_iterable = [self.pack(item) for item in obj]
                return ITERABLE_LABEL, data_type(unpacked_iterable)
            elif type(obj) in _BUILTIN_TYPES:
                return VALUE_LABEL, obj
        except Exception:
            # TODO: Log errors to a log file
            pass

        self.local_storage[id(obj)] = obj
        return REF_LABEL, (
            id(obj), obj.__class__.__name__, obj.__class__.__module__,
            inspect_methods(obj))

    @core.expose
    def execute(self, code):
        """execute a piece of code"""
        return self.pack(super(Server, self).execute(code))

    @core.expose
    def evaluate(self, expression):
        """evaluate an expression and return its result"""
        return self.pack(super(Server, self).evaluate(expression))

    @core.expose
    def invokeBuiltin(self, builtin, args, kwargs):
        args = [self.unpack(arg) for arg in args]
        kwargs = {key: self.unpack(value) for key, value in kwargs.iteritems()}
        return self.pack(
            super(Server, self).invokeBuiltin(builtin, args, kwargs))

    @core.expose
    def invokeModule(self, dottedname, args, kwargs):
        args = [self.unpack(arg) for arg in args]
        kwargs = {key: self.unpack(value) for key, value in kwargs.iteritems()}

        # dottedname is something like "os.path.walk" so strip off the module name
        modulename, dottedname = dottedname.split('.', 1)
        module = sys.modules[modulename]
        # Look up the actual method to call.
        # Because Flame already opens all doors, security wise, we allow ourselves to
        # look up a dotted name via object traversal. The security implication of that
        # is overshadowed by the security implications of enabling Flame in the first place.
        # We also don't check for access to 'private' methods. Same reasons.
        method = module
        for attr in dottedname.split('.'):
            method = getattr(method, attr)
        if callable(method):
            return self.pack(method(*args, **kwargs))
        return self.pack(method)

    @core.expose
    def getattr(self, object, name):
        # Get the attribute of the object, maybe it can be done on the automatically by calling __getattr__?
        object = self.unpack(object)
        return self.pack(getattr(object, name))

    @core.expose
    def setattr(self, object, name, value):
        # Get the attribute of the object, maybe it can be done on the automatically by calling __getattr__?
        object = self.unpack(object)
        value = self.unpack(value)
        setattr(object, name, value)

    @core.expose
    def delattr(self, object, name):
        object = self.unpack(object)
        delattr(object, name)

    @core.expose
    def call(self, object, args, kwargs):
        args = [self.unpack(arg) for arg in args]
        kwargs = {key: self.unpack(value) for key, value in kwargs.iteritems()}
        object = self.unpack(object)
        if isinstance(object, str):
            object = self.unpack(self.evaluate(object))
            return self.pack(object(*args, **kwargs))
        return self.pack(object(*args, **kwargs))

    @core.expose
    def callattr(self, object, name, args, kwargs):
        args = [self.unpack(arg) for arg in args]
        kwargs = {key: self.unpack(value) for key, value in kwargs.iteritems()}
        object = self.unpack(object)
        return self.pack(getattr(object, name)(*args, **kwargs))

    @core.expose
    def dir(self, object):
        object = self.unpack(object)
        return self.pack(dir(object))

    @core.expose
    def str(self, object):
        return self.pack(self.unpack(object).__str__())

    @core.expose
    def repr(self, object):
        return self.pack(self.unpack(object).__repr__())


def main(args=None, returnWithoutLooping=False):
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-H", "--host", default="localhost",
                      help="hostname to bind server on (default=%default)")
    parser.add_option("-p", "--port", type="int", default=0,
                      help="port to bind server on")
    parser.add_option("-u", "--unixsocket",
                      help="Unix domain socket name to bind server on")
    parser.add_option("-q", "--quiet", action="store_true", default=False,
                      help="don't output anything")
    parser.add_option("-k", "--key", help="the HMAC key to use")
    options, args = parser.parse_args(args)

    if not options.quiet:
        print("Starting Pyro Flame server.")

    hmac = (options.key or "").encode("utf-8")
    if not hmac and not options.quiet:
        print("Warning: HMAC key not set. Anyone can connect to this server!")

    config.SERIALIZERS_ACCEPTED = {"pickle"}

    daemon = core.Daemon(host=options.host, port=options.port,
                         unixsocket=options.unixsocket)

    if hmac:
        daemon._pyroHmacKey = hmac

    uri = start(daemon)
    if not options.quiet:
        print("server uri: %s" % uri)
        print("server is running.")

    if returnWithoutLooping:
        return daemon, uri  # for unit testing
    else:
        daemon.requestLoop()
    daemon.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
