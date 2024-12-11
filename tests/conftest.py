from __future__ import annotations

import contextlib
import os
import pathlib
import sys

if pathlib.Path("/cds/group/pcds").exists():
    on_cds_nfs = True
else:
    on_cds_nfs = False


@contextlib.contextmanager
def cli_args(args):
    """
    Context manager for running a block of code with a specific set of
    command-line arguments.
    """
    prev_args = sys.argv
    sys.argv = args
    yield
    sys.argv = prev_args


@contextlib.contextmanager
def pushd(directory: str | pathlib.Path):
    """
    Context manager for changing to a specific directory for a code block.
    """
    cwd = os.getcwd()
    os.chdir(directory)
    yield
    os.chdir(cwd)
