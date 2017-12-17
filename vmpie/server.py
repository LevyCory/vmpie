import sys
from Pyro4.utils.flame import Flame
from Pyro4 import constants, errors, core

class Server(Flame):
    """
    The actual FLAME server logic.
    Usually created by using :py:meth:`core.Daemon.startFlame`.
    Be *very* cautious before starting this: it allows the clients full access to everything on your system.
    """

    def __init__(self):
        self.local_storage = {}
        super(self, Flame).__init__()

    def unpack(self, args):
        # TODO: Implement unpacking
        pass

    def pack(self, args):
        # TODO: Implement
        # Pack each argument as a tuple(type[reg/ref], value[real value/(oid, class, module, ,methods))
        # Check if picklable or if stream (ie: file, stdout, etc), and handle  accordingly.
        # Check if maybe we can implement RemoteFunction, RemoteMethod and RemoteSubmodule here and send it
        # instead of defining it in vmpie.
        pass

    @core.expose
    def invokeBuiltin(self, builtin, args, kwargs):
        args = self.unpack(args)
        return self.pack(super(self, Flame).invokeBuiltin(builtin, args, kwargs))

    @core.expose
    def invokeModule(self, dottedname, args, kwargs):
        args = self.unpack(args)
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
        self.pack(getattr(object, name))

    @core.expose
    def setattr(self, object, name, value):
        # Get the attribute of the object, maybe it can be done on the automatically by calling __getattr__?
        object = self.unpack(object)
        setattr(object, name, value)

    def delattr(self, object, name):
        object = self.unpack(object)
        delattr(object, name)

    def dir(self, object):
        object = self.unpack(object)
        return dir(object)

    def str(self, object):
        return object.__str__()

    def repr(self, object):
        return object.__repr__()