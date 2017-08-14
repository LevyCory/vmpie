__author__ = 'CSI-USER'
from os import path

SPINNER_SLEEP = 0.1
SESSION_KEEPER_TIMEOUT = 30
SUCCESS_RESPONSE_CODE = 200
SUCCESS_STATE = 'success'
DEFAULT_GUEST_USERNAME = 'CSI-USER'
DEFAULT_GUEST_PASSWORD = 'Password1!'
#TODO: Test if it works
DEFAULT_PLUGIN_DIRECTORY = path.join(path.dirname(__file__), "plugins")
PYTHON_FILE_REGEX = "^.+\.py$"
VM_PLUGIN_REGEX = "^.+Plugin$"
USER_PLUGIN_FOLDER = ""



# Plugin Config File
PLUGINS_CONFIG_FILE = path.join(".", "plugins.cfg")
PLUGIN_ENABLED_ATTRIBUTE = "enabled"
PLUGIN_PATH_ATTRIBUTE = "path"
PLUGIN_NAME_ATTRIBUTE = "name"
PLUGIN_OS_ATTRIBUTE = "os"
