import Pyro4
import uuid
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
        # super(RemotePlugin, self).__init__(vm)
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

        @param code:
        @return:
        """
        return self.vm._pyro_daemon.execute(code)

    def evaluate(self, code):
        """

        @param code:
        @return:
        """
        return self.vm._pyro_daemon.evaluate(code)

    def _get_modules(self):
        """
        """
        self.vm._pyro_daemon.execute("import pkgutil")
        return self.vm._pyro_daemon.evaluate("[p[1] for p in pkgutil.iter_modules()]")


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
            self._vm._pyro_daemon.execute("import %s" % self._name)
            self._imported = True
        if self._vm._pyro_daemon.evaluate(
                        "inspect.ismodule(%s.%s)" % (self._name, item)):
            return _RemoteSubModule(".".join([self._name, item]), self._vm)
        elif self._vm._pyro_daemon.evaluate(
                        "callable(%s.%s)" % (self._name, item)):
            return _RemoteFunction(".".join([self._name, item]), self._vm)
        return self._vm._pyro_daemon.evaluate("%s.%s" % (self._name, item))


class _RemoteSubModule(object):
    """
    """
    def __init__(self, module_name, vm):
        self._name = module_name
        self._vm = vm

    def __getattr__(self, item):
        if self._vm._pyro_daemon.evaluate(
                        "inspect.ismodule(%s.%s)" % (self._name, item)):
            return _RemoteSubModule(".".join([self._name, item]), self._vm)
        elif self._vm._pyro_daemon.evaluate(
                        "inspect.isfunction(%s.%s)" % (self._name, item)):
            return _RemoteFunction(".".join([self._name, item]), self._vm)
        return self._vm._pyro_daemon.evaluate("%s.%s" % (self._name, item))


class _RemoteFunction(object):
    """
    """
    def __init__(self, function_name, vm):
        self._name = function_name
        self._vm = vm

    def __call__(self, *args, **kwargs):
        return self._vm._pyro_daemon.invokeModule(self._name, args, kwargs)
        # return self._vm._pyro_daemon.evaluate("%s()", %self.name)
        # Need to handle args too


class _RemoteFile(object):
    """

    """
    def __init__(self, path, mode, _pyro_daemon):
        self.__daemon = _pyro_daemon
        self._name = "file_{id}".format(id=uuid.uuid4().get_hex())

        self.__daemon.execute("{name} = open('{path}', '{mode}')".format(name=self._name, path=path, mode=mode))

    def __enter__(self):
        """

        @return:
        """
        raise NotImplementedError

    def __exit__(self):
        """

        @return:
        """
        raise NotImplementedError

    def close(self):
        """

        @return:
        """
        self.__daemon.execute("{name}.close()".format(name=self._name))

    @property
    def closed(self):
        """

        @return:
        """
        return self.__daemon.evaluate("{name}.closed".format(name=self._name))

    @property
    def encoding(self):
        """

        @return:
        """
        return self.__daemon.evaluate("{name}.encoding".format(name=self._name))

    def fileno(self):
        """

        @return:
        """
        return self.__daemon.evaluate("{name}.fileno()".format(name=self._name))

    def write(self, data):
        """

        @param data:
        @return:
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
        pass

    def seek(self):
        pass

    def tell(self):
        pass
