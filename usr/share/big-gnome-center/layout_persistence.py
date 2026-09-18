# SPDX-License-Identifier: MIT
"""Load the persistence protocol owned by comm-gnome-config."""

import importlib.util
from pathlib import Path

PROTOCOL_MODULE = Path('/usr/share/comm-gnome-config/dconf_persistence.py')


def open_store(path):
    if not PROTOCOL_MODULE.is_file():
        raise OSError(
            'Update comm-gnome-config before applying layouts (persistence protocol missing)'
        )
    spec = importlib.util.spec_from_file_location('comm_dconf_persistence', PROTOCOL_MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.PROTOCOL != 1:
        raise OSError('Unsupported comm-gnome-config persistence protocol')
    return module.Store(path)
