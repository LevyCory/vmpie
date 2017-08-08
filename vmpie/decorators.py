from exceptions import NotConnectedException
import utils


def is_connected(f):
    def wrapper(*args, **kwargs):
        vcenter = utils.get_vcenter()
        if vcenter.is_connected():
            return f(*args, **kwargs)
        raise NotConnectedException
    return wrapper
