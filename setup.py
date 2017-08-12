from setuptools import setup, find_packages

setup(
    name='vmpie',
    version='0.1',
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
        'pyvmomi-tools',
        'urllib3'
    ]
)
