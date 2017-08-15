__author__ = 'avital'


class VMWareToolsException(Exception):
    message = "Vmware tools are not running."

    def __init__(self):
        super(VMWareToolsException, self).__init__(self.message)


class ObjectNotFoundException(Exception):
    message = "Object was not found."

    def __init__(self):
        super(ObjectNotFoundException, self).__init__(self.message)


class NotConnectedException(Exception):
    message = "Not connected to host."

    def __init__(self):
        super(NotConnectedException, self).__init__(self.message)


class InvalidStateException(Exception):
    message = "Object is not in valid state for current operation: {state}"

    def __init__(self, message=message, state="Not specified"):
        super(InvalidStateException, self).__init__(message.format(state=state))
