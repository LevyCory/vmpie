__author__ = 'avital'
import pkg_resources
import logging
import requests
from vmpie.plugin import _collect_plugins

requests.packages.urllib3.disable_warnings()
logging.getLogger('requests.packages.urllib3').setLevel(logging.CRITICAL)

for ep in pkg_resources.iter_entry_points('vmpie.subsystems'):
    globals()[ep.name] = ep.load()


def set_vcenter(vcenter):
    globals()['vcenter'] = vcenter

#TODO: Test if it works
globals()["_plugins"] = tuple(_collect_plugins([]))