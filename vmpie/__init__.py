__author__ = 'avital'
import pkg_resources
import logging
import requests
from vmpie.plugin import PluginManager
from vmpie.consts import PLUGINS_CONFIG_FILE

requests.packages.urllib3.disable_warnings()
logging.getLogger('requests.packages.urllib3').setLevel(logging.CRITICAL)

for ep in pkg_resources.iter_entry_points('vmpie.subsystems'):
    globals()[ep.name] = ep.load()


def set_vcenter(vcenter):
    globals()['vcenter'] = vcenter


globals()["_plugin_manager"] = PluginManager()

