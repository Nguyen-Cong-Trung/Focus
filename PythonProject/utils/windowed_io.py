"""Provide writable sinks for libraries used by pythonw/windowed executables."""
import os
import sys


def ensure_standard_streams():
    # Windowed Windows programs have no console and Python sets these to None.
    # Libraries can still print startup warnings before our file logger starts.
    for name in ('stdout', 'stderr'):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, 'w', encoding='utf-8'))
