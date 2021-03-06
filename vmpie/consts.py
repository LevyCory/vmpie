from os import path

SPINNER_SLEEP = 0.1
SESSION_KEEPER_TIMEOUT = 30
SUCCESS_RESPONSE_CODE = 200
SUCCESS_STATE = 'success'
DEFAULT_GUEST_USERNAME = 'CSI-USER'
DEFAULT_GUEST_PASSWORD = 'Password1!'
# TODO: Test if it works
PYTHON_FILE_EXTENSION = ".py"
PYTHON_FILE_REGEX = "^.+\.py$"
VM_PLUGIN_REGEX = "^.+Plugin$"

# Plugin Config File
# TODO: make ot cross platform and not hardcoded
USER_PLUGIN_FOLDER = "/Users/corylevy/Projects/vmpie/plugins"
PLUGINS_CONFIG_FILE = path.join(USER_PLUGIN_FOLDER, "plugins.cfg")
BUILTIN_PLUGIN_FOLDER = path.join(path.dirname(__file__), "builtin_plugins")
BUILTIN_PLUGINS_CONFIG_FILE = path.join(BUILTIN_PLUGIN_FOLDER, "plugins.cfg")
PLUGIN_ENABLED_ATTRIBUTE = "enabled"
PLUGIN_PATH_ATTRIBUTE = "path"
PLUGIN_NAME_ATTRIBUTE = "name"
PLUGIN_OS_ATTRIBUTE = "os"
DEFAULT_SERIALIZER = "pickle"

