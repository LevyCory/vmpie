__author__ = 'avital'
import logging

import pkg_resources
import plugin
import requests

requests.packages.urllib3.disable_warnings()
logging.getLogger('requests.packages.urllib3').setLevel(logging.CRITICAL)

# Create the plugin manager and load enabled plugins
_temp_plugin_manager = plugin.PluginManager()
globals()["_plugins"] = _temp_plugin_manager.collect_plugins()

# Save the plugin manager to a global variable and delete the temp placeholder
globals()["_plugin_manager"] = _temp_plugin_manager
del _temp_plugin_manager

for ep in pkg_resources.iter_entry_points('vmpie.subsystems'):
    globals()[ep.name] = ep.load()


def set_vcenter(vcenter):
    globals()['vcenter'] = vcenter

