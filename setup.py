from setuptools import setup, find_packages

setup(
    name='vmpie',
    version='0.1a',
    packages=find_packages(),
    author='',
    entry_points={
        'vmpie.subsystems':
            [
                'VCenter = vmpie.vcenter:VCenter'
            ],
        'console_scripts':
            [
                'vmplugin = vmpie.vmplugin:main'
            ]
    },
    install_requires=[
        'pyVmomi',
        'requests',
        'six>=1.7.3',
        # FIXME: pyvmoni-tools is not in the PyPI and therefore cannot be a dependency.
        # 'pyvmomi_tools',
        'Pyro4',
        'urllib3'
    ]
)
