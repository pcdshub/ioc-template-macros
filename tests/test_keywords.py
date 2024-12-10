"""
Unit tests for individual supported keywords in expand.py
"""

import pathlib

import pytest

from expand import main

from .conftest import cli_args, pushd


def test_translate(tmp_path: pathlib.Path):
    """
    Unit test included here because the TRANSLATE keyword broke and needed to be fixed.
    """
    config = "TRIG=2"
    template = 'AFTER.B.COMES.$$TRANSLATE(TRIG,"0123456789AB","ABCDEFGHIJKL")'
    expected = "AFTER.B.COMES.C"

    config_path = tmp_path / "translate.cfg"
    template_path = tmp_path / "template.txt"
    output_path = tmp_path / "output.cfg"

    with open(config_path, "w") as fd:
        fd.write(config)

    with open(template_path, "w") as fd:
        fd.write(template)

    with cli_args(
        ["expand", "-c", str(config_path), str(template_path), str(output_path)]
    ):
        main()

    with open(output_path, "r") as fd:
        result = fd.read()

    assert result == expected


def test_standard_up_path(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture):
    """
    Unit test included because testing the $$UP(PATH) construct is skipped otherwise.

    This is because test_expand is only testing how we fill templates, not how we
    find templates.

    This string is included in a config file (not a template) in order to reference
    the encapsulating IOC directory.

    It is used in a preprocessing step to find where the templates directory is.

    The expected behavior is for this string to be replaced by the directory above
    the user's working directory, and then returned to us as in RULES_EXPAND:

        IOC_APPL_TOP = $$(shell $(EXPAND) -c $(1).cfg RELEASE)

    This specific combination is tested because it is used extensively in
    common IOCs with a children folder.
    """
    config = "RELEASE=$$UP(PATH)"

    with open(tmp_path / "up-path-test.cfg", "w") as fd:
        fd.write(config)

    with pushd(tmp_path):
        with cli_args(["expand", "-c", "up-path-test.cfg", "RELEASE"]):
            capsys.readouterr()
            main()
            outerr = capsys.readouterr()

    assert outerr.out.strip() == f"{tmp_path.parent}"
