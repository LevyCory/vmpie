import Pyro4
import vmpie.consts as consts
import vmpie.plugin as plugin


class RemotePlugin(plugin.Plugin):
    """
    """
    _name = "remote"
    _os = [plugin.UNIX, plugin.WINDOWS]

    def __init__(self, vm):
        """
        """
        super(RemotePlugin, self).__init__(vm)

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

    def _get_modules(self):
        """
        """
        self.vm._pyro_deamon.execute("import pkgutil")
        return self.vm._pyro_deamon.evaluate("[p[1] for p in pkgutil.iter_modules()]")


class _RemoteModule(object):
    """
    """
    def __init__(self, module_name, vm):
        self._name = module_name
        self._vm = vm
        self._imported = False

    def __getattr__(self, item):
        """
        """
        if not self._imported:
            self._vm._pyro_deamon.execute("import %s" % self._name)
            self._imported = True
        if self._vm._pyro_deamon.evaluate(
                        "inspect.ismodule(%s.%s)" % (self._name, item)):
            return _RemoteSubModule(".".join([self._name, item]), self._vm)
        elif self._vm._pyro_deamon.evaluate(
                        "callable(%s.%s)" % (self._name, item)):
            return _RemoteFunction(".".join([self._name, item]), self._vm)
        return self._vm._pyro_deamon.evaluate("%s.%s" % (self._name, item))


class _RemoteSubModule(object):
    """
    """
    def __init__(self, module_name, vm):
        self._name = module_name
        self._vm = vm

    def __getattr__(self, item):
        if self._vm._pyro_deamon.evaluate(
                        "inspect.ismodule(%s.%s)" % (self._name, item)):
            return _RemoteSubModule(".".join([self._name, item]), self._vm)
        elif self._vm._pyro_deamon.evaluate(
                        "inspect.isfunction(%s.%s)" % (self._name, item)):
            return _RemoteFunction(".".join([self._name, item]), self._vm)
        return self._vm._pyro_deamon.evaluate("%s.%s" % (self._name, item))


class _RemoteFunction(object):
    """
    """
    def __init__(self, function_name, vm):
        self._name = function_name
        self._vm = vm

    def __call__(self, *args, **kwargs):
        return self._vm._pyro_deamon.invokeModule(self._name, args, kwargs)
        # return self._vm._pyro_deamon.evaluate("%s()", %self.name)
        # Need to handle args too
