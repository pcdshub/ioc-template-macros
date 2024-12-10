"""
Unit tests for individual supported keywords in expand.py
"""

import pathlib

from expand import main

from .conftest import cli_args


def test_translate(tmp_path: pathlib.Path):
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
