import os
import pathlib
import re

import pytest

from expand import main

from .conftest import ON_CDS_NFS, cli_args


def get_release_dir(config_file: pathlib.Path) -> str:
    release_dir = None
    with open(config_file, "r") as fd:
        for line in fd:
            if line.startswith("RELEASE") and "=" in line:
                release_dir = line.split("=")[1].strip()
                break

    # release_dir should be something like /reg/g/pcds/epics/ioc/common/ims/R6.7.0
    if not isinstance(release_dir, str):
        raise RuntimeError(f"No release dir found for {config_file}!")
    return release_dir


def get_template_dir_from_release_dir(release_dir: str) -> pathlib.Path:
    release_dir = release_dir.removesuffix("/")
    long_path, version_str = os.path.split(release_dir)
    long_path, common_name = os.path.split(long_path)

    # something like .../ioc-template-macros/tests/common/ims/R6.7.0
    return (
        pathlib.Path(__file__).parent
        / "artifacts"
        / "common"
        / common_name
        / version_str
    )


examples = pathlib.Path(__file__).parent / "artifacts" / "examples"
configs = {pth.name: pth for pth in examples.glob("**/*.cfg")}
template_globs = [
    "Makefile",
    "st.cmd",
    "edm-ioc.cmd",
    "pydm-ioc.cmd",
    "launchgui-ioc.cmd",
    "syncts-ioc.cmd",
    "ioc.*",
    "*.sh",
]

variants = []


def init_variants():
    variants.clear()
    for cfg_name, config_file in configs.items():
        this_cfg_templates = []
        release_dir = get_release_dir(config_file=config_file)
        template_dir = get_template_dir_from_release_dir(release_dir=release_dir)
        for pattern in template_globs:
            if list(template_dir.glob(pattern=pattern)):
                this_cfg_templates.append(pattern)
        if not this_cfg_templates:
            raise RuntimeError(
                f"Did not find any templates for {cfg_name} ({config_file})"
            )
        for template in this_cfg_templates:
            variants.append((cfg_name, template))


init_variants()


@pytest.mark.parametrize(
    "cfg_name,template",
    variants,
)
def test_expand_full(tmp_path: pathlib.Path, cfg_name: str, template: str):
    """
    Check that each config file can be used with expand.py.

    Command-line direct testing of expand.py is something like:
    expand -c config_file template_file output_file

    The Makefiles automate this process for real IOC builds.
    This looks something like:

        @$(EXPAND) -c $(1).cfg $$(<) $$@ IOCNAME=$(1) TOP=$(BUILD_TOP_ABS) IOCTOP=$(IOC_APPL_TOP)

    Where:
    - $(EXPAND) gets replaced with our "expand" script (which calls expand.py)
    - $(1).cfg gets filled in with the config file
    - $$(<) gets filled in with the first prerequisite, which ends up being a
      template file
    - $$@ gets filled in with the target filename
    - The rest get passed in as "additional arguments" (undocumented),
      but all this does is treat the config file as if it starts with those
      declarations on separate lines.
      Effectively, this adds additional variable definitions from RULES_EXPAND:

      - IOCNAME gets set to the name of the config file, without .cfg
      - TOP gets set to the absolute path to the "build" directory.
        The "build" directory is e.g.
        /cds/group/pcds/epics/ioc/xpp/gigECam/R2.0.7/build
      - IOCTOP ultimately gets set to whatever the RELEASE line in the config file is.

    There is an additional undocumented "expand -c config_file name" syntax
    that initially appears unused, but it's actually used to generate a
    shell script named IOC_APPL_TOP that sets IOC_APPL_TOP to the RELEASE line.
    Bizarre behavior. The overall goal for this is apparently to locate the
    RELEASE directory in a preprocessing step. This will be tested separately.

    For the test here, we want to generate files one by one
    and check that they are correct (no regressions)
    """  # noqa: E501
    config_file = configs[cfg_name]
    # Something like /cds/group/pcds/epics/ioc/common/gigECam/R5.0.5
    release_dir = get_release_dir(config_file=config_file)
    # Something like ../ioc-template-macros/tests/common/gigECam/R5.0.5
    template_dir = get_template_dir_from_release_dir(release_dir=release_dir)
    version_str = template_dir.name
    common_name = template_dir.parent.name

    template_files = list(template_dir.glob(template))
    if not template_files:
        raise RuntimeError(
            "Test collection error, should not check "
            f"{template} for {common_name}/{version_str}."
        )

    iocname = config_file.stem
    build_dir = str(tmp_path)
    for template_file in template_files:
        if "ioc" in template:
            target_file = tmp_path / template_file.name.replace("ioc", iocname)
        else:
            target_file = tmp_path / template_file.name
        with cli_args(
            [
                "expand",
                "-c",
                str(config_file),
                str(template_file),
                str(target_file),
                f"IOCNAME={iocname}",
                f"TOP={build_dir}",
                f"IOCTOP={release_dir}",
            ]
        ):
            main()

        assert target_file.exists()
        with open(target_file, "r") as fd:
            output_lines = fd.read().splitlines()
        expected_file = (
            pathlib.Path(__file__).parent
            / "artifacts"
            / "expected"
            / common_name
            / iocname
            / target_file.name
        )
        if not expected_file.exists():
            # Oh no, maybe it's somewhere nearby! IOCs get renamed sometimes...
            glob_paths = list(
                (pathlib.Path(__file__).parent / "artifacts" / "expected").glob(
                    f"**/{iocname}/{target_file.name}"
                )
            )
            if not glob_paths:
                # Argh
                raise RuntimeError(f"Cannot find {expected_file} in test.")
            elif len(glob_paths) == 1:
                # Phew, we found it!
                expected_file = glob_paths[0]
            else:
                # We found... two or more???
                raise RuntimeError(
                    f"Found more than one alternate candidate for {expected_file} "
                    f"in test: {glob_paths}"
                )
        with open(expected_file, "r") as fd:
            expected_lines = fd.read().splitlines()
        failure_info = (
            f"Regression in using config file {config_file} "
            f"to expand template file {template_file} "
            f"to make {target_file.name}. "
            f"Expected to match {expected_file}."
        )
        if len(output_lines) != len(expected_lines):
            # Maybe the line difference is from a missing $$INCLUDE file
            maybe_skip_include(template_file=template_file)
        assert len(output_lines) == len(expected_lines), failure_info
        working_dir = os.getcwd()
        for output, expected in zip(output_lines, expected_lines):
            # Preprocessing: /reg/g/ -> /cds/group/ for fair comparison
            output = normalize_reg(output)
            expected = normalize_reg(expected)
            if build_dir in output:
                # Special case 1: our pytest build dir is not the real build dir
                assert full_match_ignoring_test_artifact(
                    text=output, test_artifact=build_dir, expected=expected
                )
            elif working_dir in output:
                # Special case 2: our cwd is not the same cwd as the original make
                assert full_match_ignoring_test_artifact(
                    text=output, test_artifact=working_dir, expected=expected
                )
            else:
                assert output == expected, failure_info


def maybe_skip_include(template_file: pathlib.Path) -> None:
    """
    Skip this test if we know it can't be done.

    For example, tests that reference files from the CDS system can't be run
    on CI. They need to have access to NFS.
    """
    if ON_CDS_NFS:
        return
    with open(template_file, "r") as fd:
        if "$$INCLUDE" in fd.read():
            pytest.skip(
                reason="Real test with INCLUDE macro cannot be done without NFS."
            )


def full_match_ignoring_test_artifact(
    text: str, test_artifact: str, expected: str
) -> bool:
    """
    Return True if text and expected are equal, except for instances of test_artifact.

    This is useful when we don't have the original paths at build time,
    so we expect that the test suite output only differs from the original output
    in a small number of places.
    """
    text = text.replace(test_artifact, ".*")
    for special_char in "()$":
        text = text.replace(special_char, f"\\{special_char}")
    text = f"^{text}$"
    return re.fullmatch(text, expected)


def normalize_reg(text: str) -> str:
    """
    /reg/g/ -> /cds/group
    """
    return text.replace("/reg/g/", "/cds/group/")


config_vars = {
    "RELEASE": "/some/release/path",
    "ENGINEER": "Mr. Beckhoff",
    "LOCATION": "Hammer space",
    "ASDF": "asdfasdf",
}


@pytest.mark.parametrize(
    "config_var",
    list(config_vars),
)
def test_expand_preprocessing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture, config_var: str
):
    """
    Before we fill a template, we can inspect the .cfg file using expand.py.

    This has some pretty involved specifications in the source code that
    involve including macros inside the config file itself.

    I'll ignore all of this and test the most basic thing, which is actually
    used in RULES_EXPAND: checking variables values from the cfg file.

    This is typically used to get the RELEASE path:

        IOC_APPL_TOP = $$(shell $(EXPAND) -c $(1).cfg RELEASE)

    Often this is combined with the "UP" macro:
    see test_keywords::test_standard_up_path where we test this macro.
    """
    cfg_file = tmp_path / "test-expand-processing.cfg"
    with open(cfg_file, "w") as fd:
        for key, value in config_vars.items():
            fd.write(f"{key}={value}\n")

    with cli_args(["expand", "-c", str(cfg_file), config_var]):
        capsys.readouterr()
        main()
        outerr = capsys.readouterr()

    assert outerr.out.strip() == config_vars[config_var]
