"""Make an unhandled exception exit NON-ZERO. Import this first in any tool that gates.

    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _hardfail  # noqa: F401

WHY. `blender -b --python foo.py` returns **0 even when the script raised**. This project
recorded that once and then walked straight into it again: `seam_bake.py` died on a NameError
mid-way, printed a traceback, wrote no attribute — and the shell reported success. Anything
chaining these tools would have carried on with a half-written file.

An explicit `sys.exit(1)` does propagate (verified: `cavity_gate.py` returns 1 on FAIL). It is
only the *unhandled* path that lies, which is the dangerous one — a gate that crashes is a
gate that did not run, and it must never be mistaken for a gate that passed.
"""
import sys
import os


def _hook(exc_type, exc, tb):
    sys.__excepthook__(exc_type, exc, tb)
    sys.stdout.flush()
    sys.stderr.flush()
    # os._exit bypasses Blender's own shutdown, which is what swallows the status
    os._exit(1)


sys.excepthook = _hook
