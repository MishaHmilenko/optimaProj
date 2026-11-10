"""SINGLETON, as a reusable metaclass.

Any class using SingletonMeta has at most one instance per process:
calling the class again returns the instance created the first time.
Each class gets its own instance (subclasses are not shared with their
parents), which is what lets every concrete element factory be its own
singleton.
"""

from __future__ import annotations

import threading
from abc import ABCMeta
from typing import Any


class SingletonMeta(ABCMeta):
    """Derives from ABCMeta so it can be used together with ABC base
    classes (the abstract factory is an ABC)."""

    _instances: dict[type, Any] = {}
    _lock = threading.Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in SingletonMeta._instances:
            with SingletonMeta._lock:
                # Double-checked: another thread may have created it while
                # this one was waiting for the lock.
                if cls not in SingletonMeta._instances:
                    SingletonMeta._instances[cls] = super().__call__(*args, **kwargs)
        return SingletonMeta._instances[cls]
