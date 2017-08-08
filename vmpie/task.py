import consts
import time
from pyvmomi_tools import cli


class Task(object):

    def __init__(self, _pyVmomiTask=None):
        self._pyVmomiTask = _pyVmomiTask
        self.created_at = self._pyVmomiTask.info.queueTime
        self.started_at = self._pyVmomiTask.info.startTime

    @property
    def state(self):
        return self._pyVmomiTask.state.lower()

    @property
    def name(self):
        return self._pyVmomiTask.name

    @property
    def is_alive(self):
        return self._pyVmomiTask.is_alive

    @property
    def completed_at(self):
        return self._pyVmomiTask.info.completeTime or None

    @property
    def onwer(self):
        return self._pyVmomiTask.info.result.userName or None

    def is_success(self):
        return self.state == consts.SUCCESS_STATE

    def wait(self):
        self._pyVmomiTask.wait()

    def wait_with_spinner(self, condition, argument, msg):
        while condition(argument):
            # Outputs to stdout - might be a problem when silencing logs
            cli.cursor.spinner(msg)
            time.sleep(consts.SPINNER_SLEEP)

    def __str__(self):
        return '<Task: {task_name}, {state}: >'.format(task_name=self.name,
                                                       state=self.state)
# TODO: Guest-Tasks (ie: reboot)
