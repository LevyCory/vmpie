__author__ = 'CSI-USER'
import os

SPINNER_SLEEP = 0.1
SESSION_KEEPER_TIMEOUT = 30
SUCCESS_RESPONSE_CODE = 200
SUCCESS_STATE = 'success'
DEFAULT_GUEST_USERNAME = 'CSI-USER'
DEFAULT_GUEST_PASSWORD = 'Password1!'
#TODO: Test if it works
DEFAULT_PLUGIN_DIRECTORY = os.path.join(os.path.dirname(__file__), "plugins")
PYTHON_FILE_REGEX = "^.+\.py$"
VM_PLUGIN_REGEX = "^.+Plugin$"
