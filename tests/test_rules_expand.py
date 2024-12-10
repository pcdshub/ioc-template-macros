import pathlib
import shutil
import subprocess

import pytest

from .conftest import pushd


@pytest.mark.parametrize(
    "target,expected",
    [
        ("ioc-tst-unittest1", [1]),
        ("ioc-tst-unittest2", [2]),
        ("ioc-tst-unittest3", [3]),
        ("", [1, 2, 3]),
    ],
)
def test_rules_expand(tmp_path: pathlib.Path, target: str, expected: list[int]):
    """
    Build one or more instance of ioc-tst-unittest.

    This uses whichever RULES_EXPAND is in the local clone.
    The IOCs are built in the pytest temp folder.
    """
    # Copy the entire source test into the temp folder
    ioc_source = pathlib.Path(__file__).parent / "ioc-tst-unittest"
    shutil.copytree(ioc_source, tmp_path / "ioc-tst-unittest")
    # Create the children Makefile
    rules_expand = pathlib.Path(__file__).parent.parent / "RULES_EXPAND"
    children_dir = tmp_path / "ioc-tst-unittest" / "children"
    with open(children_dir / "Makefile", "w") as fd:
        fd.write("IOC_CFG += $(wildcard *.cfg)\n")
        fd.write(f"include {rules_expand}\n")
    with pushd(children_dir):
        args = ["make"]
        if target:
            args.append(target)
        subprocess.run(args, check=True)
    for num in expected:
        ioc_name = f"ioc-tst-unittest{num}"
        ioc_bld_path = children_dir / "build" / "iocBoot" / ioc_name
        for filename in [
            f"edm-{ioc_name}.cmd",
            f"{ioc_name}.sub-arch",
            f"{ioc_name}.sub-req",
            f"launchgui-{ioc_name}.cmd",
            f"pydm-{ioc_name}.cmd",
            "some_script.sh",
            "st.cmd",
            f"syncts-{ioc_name}.cmd",
        ]:
            bld_path = ioc_bld_path / filename
            with open(bld_path, "r") as fd:
                text = fd.read().splitlines()
            # Did each of the templateable files get templated?
            assert text[0] == "Unit test"
            assert text[1] == "pytest"
            assert text[2] == f"IOC:TST:UNITTEST{num}"
        # Did IOC_APPL_TOP get created with the correct contents?
        with open(ioc_bld_path / "IOC_APPL_TOP", "r") as fd:
            text = fd.read().strip()
        assert text == f"IOC_APPL_TOP={children_dir.parent}"
        # Did the Makefile get copied over?
        assert (ioc_bld_path / "Makefile").exists()
        # Did the inner Makefile get run?
        assert (ioc_bld_path / "we_ran_make.txt").exists()
