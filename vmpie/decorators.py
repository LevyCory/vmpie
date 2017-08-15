import utils
import vmpie_exceptions


def connected(func):
    def wrapper(*args, **kwargs):
        vcenter = utils.get_vcenter()
        if vcenter.is_connected():
            return func(*args, **kwargs)
        raise vmpie_exceptions.NotConnectedException
    return wrapper
