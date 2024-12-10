"""
This is a script to generate the contents of the common, examples, and expected folders.

Some of this information is not trivially available to a web consumer, so I'm
opting to generate it via copying from deployed filesystem locations.

This would allow us to run unit tests that reference real configurations
on the GitHub actions CI.
"""

from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
import typing

logger = logging.getLogger(__name__)

# Add an ioc name to BANNED_IOCs to skip all IOCs that would otherwise
# be sorted into these names.
# Only ban IOCs that are malformed,
# failing the test with a file not found error and such
# or e.g. IOC name duplication that creates ambiguity.
BANNED_IOC_TYPES = [
    "edtCam",  # not used any more and lots of IOC name duplications come from it
    "hpi_6012",  # most recent build has a missing file so we can't check against it
    "gigEcam",  # annoying typo breaks some things (should have been gigECam)
    "leviton",  # renamed to pdu_snmp, also similar name typo hell
    "Leviton",  # renamed to pdu_snmp, also similar name typo hell
    "Levitons",  # renamed to pdu_snmp, also similar name typo hell
    "optics-notepad",  # renamed to optics-pitch-notepad
    "pnccd",  # very old, not used, has super old path names that are a distraction
    "RohdeSchwartzNGPS",  # pnccd support IOC with same issues as pnccd ioc
    "topas",  # latest release broken (failed build), not deployed in iocmanager
    "tricatt",  # typo (tricam) and failed build
]
# Special cases: only for IOCs whose latest versions have build errors!
BANNED_IOC_NAMES = [
    # These scope IOCs must have had an NFS issue during the build.
    # The example files just say "this path doesn't exist!" (but it does)
    "ioc-cxi-scope-portable01",
    "ioc-cxi-scope-portable02",
    # These IOCs' releases were hand-edited...
    "ioc-cxi-setra",
    "ioc-las-ftl-mcs2-01",
    "ioc-las-ftl-mcs2-02",
    "ioc-mfx-hera-smc100",
    "ioc-tmo-mcs2-01",
    "ioc-xpp-ensemble-01",
]
# Focus on the targets of expand.py from RULES_EXPAND
# Avoid other potentially large files
VALID_EXPAND_GLOBS = [
    "Makefile",
    "st.cmd",
    "edm-*.cmd",
    "pydm-*.cmd",
    "launchgui-*.cmd",
    "syncts-*.cmd",
    "*.sh",
    # Missing here is iocname.*, handle later when we know iocname
]
# Save time in the recursive search for templated iocs
SKIP_SEARCH_DIRS = [
    ".git",
    ".svn",
    "build",
]


def generate_examples(
    ioc_deploy_path: pathlib.Path, examples_path: pathlib.Path
) -> None:
    """
    Generate the examples filder.

    Fills examples_path with the latest versions of .cfg files from
    under the ioc_deploy_path tree.
    """
    if not ioc_deploy_path.is_dir() or not examples_path.is_dir():
        raise ValueError(
            f"Expected {ioc_deploy_path} and {examples_path} to be directories."
        )
    # Should be e.g. "/cds/group/pcds/epics/ioc/xpp/gigECam/R2.0.7"
    # or e.g. "/cds/group/pcds/epics/ioc/common/bk-1697/R1.0.1/children"
    for template_ioc in iter_latest_template_iocs(ioc_deploy_path=ioc_deploy_path):
        for cfg_path in template_ioc.glob("*.cfg"):
            if cfg_path.stem in BANNED_IOC_NAMES:
                continue
            try:
                # Should be e.g. "/cds/group/pcds/epics/ioc/common/gigECam/R5.0.4"
                release_path = get_release_path(cfg_file=cfg_path)
            except InvalidReleaseError:
                logger.info(f"{cfg_path} does not have a valid release.")
                continue
            variant = release_path.parent.name
            if variant in BANNED_IOC_TYPES:
                continue
            examples_target = examples_path / variant
            examples_target.mkdir(exist_ok=True)
            log_copy(src=cfg_path, dst=examples_target)
            # We need to edit the file in place if it has $$UP(PATH) as its release
            # Since the original path had the context for the absolute release path
            new_file = examples_target / cfg_path.name
            with open(new_file, "r") as fd:
                text = fd.read()
            if "$$UP(PATH)" in text:
                new_text = text.replace("$$UP(PATH)", str(release_path))
                chmod_uplusw(path=new_file)
                with open(new_file, "w") as fd:
                    fd.write(new_text)

    chmod_uplusw(path=examples_path)


def chmod_uplusw(path: str | pathlib.Path) -> subprocess.CompletedProcess:
    """
    Make everything at path user-writable (recursively).

    The python standard library has only annoying ways to do this.
    The cli chmod tool is much more convenient.

    This is used to make sure we can write to our own directories, since
    the source files are often write-protected, and therefore are
    still write-protected after we copy them.
    """
    return subprocess.run(["chmod", "-R", "u+w", str(path)])


def log_copy(src: pathlib.Path, dst: pathlib.Path):
    """
    Copy file from src to dst, log the copy, error on copies outside of tests dir.
    """
    tests_dir = pathlib.Path(__file__).parent
    check_parent = dst
    while check_parent not in (tests_dir, check_parent.parent):
        check_parent = check_parent.parent
    if check_parent.parent == check_parent:
        raise ValueError(
            f"Cannot copy to outside the tests folder. Tried to copy to {dst}"
        )
    logger.info(f"shutil.copy(src={src}, dst={dst})")
    try:
        shutil.copy(src=src, dst=dst)
    except OSError as exc:
        logger.warning(f"File copy failed! {exc}")


def iter_latest_template_iocs(
    ioc_deploy_path: pathlib.Path,
) -> typing.Iterator[pathlib.Path]:
    """
    Yield latest versioned directories containing .cfg files.

    The path either ends in a version number, e.g. R1.0.0,
    or it ends in a version number followed by children,
    e.g. R1.0.0/children.
    """
    if not ioc_deploy_path.is_dir():
        return
    try:
        latest_version = pick_latest_version(ioc_path=ioc_deploy_path)
    except RuntimeError:
        ...
    else:
        ioc_type = latest_version.parent.name
        if ioc_type in BANNED_IOC_TYPES:
            return
        if is_template_ioc(ioc_path=latest_version):
            return (yield latest_version)
        elif is_template_ioc(ioc_path=latest_version / "children"):
            return (yield latest_version / "children")
        else:
            return
    for subpath in ioc_deploy_path.iterdir():
        if subpath.name in SKIP_SEARCH_DIRS:
            continue
        yield from iter_latest_template_iocs(ioc_deploy_path=subpath)


def pick_latest_version(ioc_path: pathlib.Path) -> pathlib.Path:
    """
    Given a directory with version-named folders, return the latest version.
    """
    latest = (0, 0, 0)
    latest_path = None
    for version_path in ioc_path.iterdir():
        try:
            version = get_version_tuple(version_str=version_path.name)
        except ValueError:
            continue
        if len(version) < 2:
            logger.info(
                f"In {ioc_path} found {version_path.name} "
                "which has fewer than 2 elements."
            )
            continue
        if version > latest:
            latest = version
            latest_path = version_path
    if latest_path is None:
        raise RuntimeError(f"No version directories in {ioc_path}")
    return latest_path


def get_version_tuple(version_str: str) -> tuple[int, int, int]:
    """
    Convert a version string like R2.0.0 to a tuple for easy comparisons.
    """
    # Avoid cases like ek9000 which otherwise parse to version 9000
    if "." not in version_str:
        raise ValueError(f"{version_str} is not a valid version.")
    orig_ver_str = version_str
    # Remove leading v, V, r, R
    while version_str and version_str[0].isalpha():
        version_str = version_str[1:]
    if not version_str:
        raise ValueError(f"{orig_ver_str} is not a valid version.")
    try:
        return tuple(int(ver) for ver in version_str.split("."))
    except ValueError as exc:
        raise ValueError(f"{orig_ver_str} is not a valid version.") from exc


def is_template_ioc(ioc_path: pathlib.Path) -> bool:
    """
    Returns True if the ioc deployed at ioc_path is a template ioc (with .cfg files)
    """
    return bool(list(ioc_path.glob("*.cfg"))) and (ioc_path / "build").is_dir()


def get_release_path(cfg_file: pathlib.Path) -> pathlib.Path:
    """
    Get the path to the release folder that cfg_file will use to build.

    This will raise if there is no release path or if the release path is not tagged.
    """
    release_dir = None
    with open(cfg_file, "r") as fd:
        for line in fd:
            if line.startswith("RELEASE") and "=" in line:
                release_dir = line.split("=")[1].strip()
                break
    # Should be e.g. "/cds/group/pcds/epics/ioc/common/gigECam/R5.0.4"
    if release_dir is None:
        raise InvalidReleaseError
    # Special case: cfg file in children folder refers to parent dir via macro
    if release_dir == "$$UP(PATH)":
        release_path = cfg_file.parent.parent
    else:
        release_path = pathlib.Path(release_dir)
    try:
        get_version_tuple(release_path.name)
    except ValueError as exc:
        raise InvalidReleaseError from exc
    return release_path


class InvalidReleaseError(RuntimeError): ...


def generate_common(examples_path: pathlib.Path, common_path: pathlib.Path) -> None:
    """
    Given config files in examples_path, generate common_path with necessary templates.

    The contents of common_path will be e.g.
    common/gigECam/R3.0.0/st.cmd

    It will not be the full IOC, just the contents of iocBoot/templates.
    This will include every template referenced by the config files in example_path.
    """
    if not examples_path.is_dir() or not common_path.is_dir():
        raise ValueError(
            f"Expected {examples_path} and {common_path} to be directories."
        )
    for cfg_file in examples_path.glob("**/*.cfg"):
        # Should be e.g. "/cds/group/pcds/epics/ioc/common/gigECam/R5.0.4"
        release_path = get_release_path(cfg_file=cfg_file)
        variant = release_path.parent.name
        if variant in BANNED_IOC_TYPES:
            continue
        version = release_path.name
        templates = release_path / "iocBoot" / "templates"
        this_cfg_common_dir = common_path / variant / version
        if this_cfg_common_dir.exists():
            logger.debug(f"{this_cfg_common_dir} already exists, skipping.")
            continue
        this_cfg_common_dir.parent.mkdir(exist_ok=True)
        this_cfg_common_dir.mkdir()
        for file_path in templates.iterdir():
            if file_path.is_file():
                log_copy(src=file_path, dst=this_cfg_common_dir)

    chmod_uplusw(path=common_path)


def generate_expected(
    ioc_deploy_path: pathlib.Path,
    examples_path: pathlib.Path,
    expected_path: pathlib.Path,
) -> None:
    """
    Given the ioc_deploy_path, generate expected_path with the real template results.

    The contents of expected_path will be e.g.
    expected/gigECam/iocname/st.cmd

    It will not be the full IOC, just the contents of build/iocBoot/iocname
    """
    if (
        not ioc_deploy_path.is_dir()
        or not examples_path.is_dir()
        or not expected_path.is_dir()
    ):
        raise ValueError(
            f"Expected {ioc_deploy_path}, {examples_path}, "
            f"and {expected_path} to be directories."
        )

    # template_ioc is something like "/cds/group/pcds/epics/ioc/xpp/gigECam/R2.0.4"
    # or, it can also be "/cds/group/pcds/epics/ioc/common/bk-1697/R1.0.1/children"
    for template_ioc in iter_latest_template_iocs(ioc_deploy_path=ioc_deploy_path):
        if template_ioc.name == "children":
            variant = template_ioc.parent.parent.name
        else:
            variant = template_ioc.parent.name

        built_iocs_subfolder = template_ioc / "build" / "iocBoot"
        for built_ioc in built_iocs_subfolder.iterdir():
            if not built_ioc.is_dir():
                continue
            if not list(examples_path.glob(f"**/{built_ioc.name}.cfg")):
                logger.info(f"{built_ioc.name}.cfg not in {examples_path}, skipping")
                continue

            iocname = built_ioc.name

            expected_path.mkdir(exist_ok=True)
            (expected_path / variant).mkdir(exist_ok=True)

            expected_ioc_target = expected_path / variant / iocname
            expected_ioc_target.mkdir(exist_ok=True)

            for glob_pattern in VALID_EXPAND_GLOBS + [f"{iocname}.*"]:
                for built_file in built_ioc.glob(glob_pattern):
                    log_copy(src=built_file, dst=expected_ioc_target)

    chmod_uplusw(path=expected_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    ioc_deploy_path = pathlib.Path("/cds/group/pcds/epics/ioc")
    examples_path = pathlib.Path(__file__).parent / "examples"
    common_path = pathlib.Path(__file__).parent / "common"
    expected_path = pathlib.Path(__file__).parent / "expected"

    areas = [
        "common",
        "cxi",
        "det",
        "kfe",
        "las",
        "lfe",
        "mec",
        "mfx",
        "rix",
        "tmo",
        "txi",
        "ued",
        "xcs",
        "xpp",
        "xrt",
    ]

    for area in areas:
        generate_examples(
            ioc_deploy_path=ioc_deploy_path / area,
            examples_path=examples_path,
        )
    generate_common(
        examples_path=examples_path,
        common_path=common_path,
    )
    for area in areas:
        generate_expected(
            ioc_deploy_path=ioc_deploy_path / area,
            examples_path=examples_path,
            expected_path=expected_path,
        )
