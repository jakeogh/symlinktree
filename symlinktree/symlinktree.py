#!/usr/bin/env python3
# -*- coding: utf8 -*-

# flake8: noqa           # flake8 has no per file settings :(
# pylint: disable=C0111  # docstrings are always outdated and wrong
# pylint: disable=C0114  #      Missing module docstring (missing-module-docstring)
# pylint: disable=W0511  # todo is encouraged
# pylint: disable=C0301  # line too long
# pylint: disable=R0902  # too many instance attributes
# pylint: disable=C0302  # too many lines in module
# pylint: disable=C0103  # single letter var names, func name too descriptive
# pylint: disable=R0911  # too many return statements
# pylint: disable=R0912  # too many branches
# pylint: disable=R0915  # too many statements
# pylint: disable=R0913  # too many arguments
# pylint: disable=R1702  # too many nested blocks
# pylint: disable=R0914  # too many local variables
# pylint: disable=R0903  # too few public methods
# pylint: disable=E1101  # no member for base
# pylint: disable=W0201  # attribute defined outside __init__
# pylint: disable=R0916  # Too many boolean expressions in if statement
# pylint: disable=C0305  # Trailing newlines editor should fix automatically, pointless warning


import os
import sys
import time
from math import inf
from pathlib import Path
from shutil import move
from typing import Union

import click
from asserttool import ic
from clicktool import click_add_options
from clicktool import click_global_options
from clicktool import tv
from eprint import eprint
from getdents import paths
from pathtool import path_is_dir

global SKIP_DIRS
SKIP_DIRS = set()


def is_broken_symlink(path: Path):
    if os.path.islink(path):  # path is a symlink
        return not os.path.exists(path)  # returns False for broken symlinks
    return False  # path isnt a symlink


def is_unbroken_symlink(path: Path):
    if os.path.islink(path):  # path is a symlink
        return os.path.exists(path)  # returns False for broken symlinks
    return False  # path isnt a symlink


def symlink_or_exit(
    *,
    target: Path,
    link_name: Path,
    confirm: bool = False,
    verbose: Union[bool, int, float],
):
    if verbose:
        ic(target)
        ic(link_name)

    if confirm:
        input(f"press enter to os.symlink({target}, {link_name})")

    try:
        os.symlink(target, link_name)
    except Exception as e:
        eprint("Got Exception: %s", e)
        eprint(f"Unable to symlink link_name: {link_name} to target: {target} Exiting.")
        raise e


def mkdir_or_exit(
    folder: Path,
    confirm: bool,
    verbose: Union[bool, int, float],
):
    if verbose:
        ic(folder)
    if confirm:
        input(f"press enter to os.makedirs({folder})")
    try:
        os.makedirs(folder)
    except Exception as e:
        ic("Exception: %s", e)
        ic(f"Unable to os.mkdir({folder}). Exiting.")
        sys.exit(1)


def move_path_to_old(
    path: Path,
    confirm: bool,
    verbose: Union[bool, int, float],
):
    path = Path(path).resolve()
    timestamp = str(time.time())
    dest = path.with_name(path.name + "._symlinktree_old." + timestamp)
    if verbose:
        ic(f"{path} -> {dest}")
    if confirm:
        input(f"press enter to move({path}, {dest})")
    move(path.as_posix(), dest)


def process_infile(
    root: Path,
    skel: Path,
    infile: Path,
    confirm: bool,
    verbose: Union[bool, int, float],
):
    assert "._symlinktree_old." not in infile.as_posix()
    global SKIP_DIRS
    eprint("")
    ic(infile)

    if infile == skel:
        return

    if root == Path("/root"):
        if infile.name == ".ssh":
            return

    if verbose:
        ic(root)
        ic(skel)

    dest_dir = Path(root / infile.relative_to(skel)).parent
    ic(dest_dir)

    possible_symlink_dir = Path(infile.parent / Path(".symlink_dir"))  # walrus!

    if possible_symlink_dir.exists():
        ic("found .symlink_dir dotfile:", possible_symlink_dir)
        SKIP_DIRS.add(infile.parent)
        ic(SKIP_DIRS)
        assert not dest_dir.is_file()

        if not dest_dir.exists():
            symlink_or_exit(
                target=infile.parent,
                link_name=dest_dir,
                confirm=confirm,
                verbose=verbose,
            )
            return

        if is_unbroken_symlink(dest_dir):
            assert dest_dir.resolve() == infile.parent
            return

        if is_broken_symlink(dest_dir):
            if is_broken_symlink(infile):
                ic(f"infile: {infile} is a broken symlink, skipping")
                return
            if verbose:
                ic("found broken symlink:", dest_dir)
                sys.exit(1)  # todo

        elif path_is_dir(dest_dir):
            move_path_to_old(
                dest_dir, confirm=confirm, verbose=verbose
            )  # might want to just rm broken symlinks
            symlink_or_exit(
                target=infile.parent,
                link_name=dest_dir,
                confirm=confirm,
                verbose=verbose,
            )
            return

    if is_broken_symlink(infile):  # dont process broken symlinks
        return

    if not infile.is_symlink():  # is_dir() returns true for symlinks to dirs
        if infile.is_dir():  # dont make symlinks to dirs unless .symlink_dir exists
            return

    dest_file = root / infile.relative_to(skel)
    ic(dest_file)
    if is_broken_symlink(dest_file):
        if is_broken_symlink(infile):
            ic(f"infile: {infile} is a broken symlink, skipping")
            return
        ic("found broken symlink at dest_file:", dest_file, "moving it to .old")
        move_path_to_old(dest_file, confirm=confirm, verbose=verbose)
    elif is_unbroken_symlink(dest_file):
        if (
            dest_file.resolve() == infile.resolve()
        ):  # must resolve() infile cuz it could also be a symlink
            ic("skipping pre-existing correctly linked dest file")
            return
        if verbose:
            ic("moving incorrectly linked symlink")
            ic(dest_file.resolve())
            ic(infile)
        move_path_to_old(dest_file, confirm=confirm, verbose=verbose)

    if not os.path.islink(dest_file):
        if dest_file.exists():
            ic(
                "attempting to move pre-existing dest file to make way for symlink dest_file:",
                dest_file,
            )
            move_path_to_old(dest_file, confirm=confirm, verbose=verbose)

    if not dest_dir.exists():
        ic("making dest_dir:", dest_dir)
        mkdir_or_exit(dest_dir, confirm=confirm, verbose=verbose)

    symlink_or_exit(
        target=infile, link_name=dest_file, confirm=confirm, verbose=verbose
    )


def skip_path(
    infile: Path,
    verbose: Union[bool, int, float],
):
    for parent in infile.parents:
        if parent in SKIP_DIRS:
            if verbose:
                ic(f"skipping: {infile} parent {parent} in SKIP_DIRS:")
            return True
    return False


def process_skel(
    root: Path,
    skel: Path,
    count: int,
    confirm: bool,
    verbose: Union[bool, int, float],
):
    if verbose:
        ic(root, skel)

    for index, infile in enumerate(
        paths(
            skel,
            return_dirs=True,
            return_files=True,
            return_symlinks=True,
            verbose=verbose,
        )
    ):
        if count:
            if index >= count:
                return
        _infile = infile.pathlib
        del infile
        if not skip_path(_infile, verbose=verbose):
            process_infile(
                root=root,
                skel=skel,
                infile=_infile,
                confirm=confirm,
                verbose=verbose,
            )


@click.command()
@click.argument(
    "sysskel",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=False,
        path_type=Path,
        allow_dash=False,
    ),
    nargs=1,
    required=True,
)
@click.option(
    "--count",
    type=int,
    required=False,
)
@click.option(
    "--re-apply-skel",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=False,
        path_type=Path,
        allow_dash=False,
    ),
    nargs=1,
    required=False,
)
@click.option(
    "--confirm",
    is_flag=True,
)
@click_add_options(click_global_options)
@click.pass_context
def cli(
    ctx,
    sysskel: Path,
    count: int,
    re_apply_skel: Path,
    verbose: Union[bool, int, float],
    verbose_inf: bool,
    dict_input: bool,
    confirm: bool,
):

    tty, verbose = tv(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
    )

    global SKIP_DIRS

    sysskel = Path(sysskel).resolve()
    assert path_is_dir(sysskel)
    if not os.path.exists(sysskel):
        ic("sysskel_dir:", sysskel, "does not exist. Exiting.")
        sys.exit(1)

    if re_apply_skel:
        ic("\n\nre-applying skel")
        path = Path(re_apply_skel)
        assert str(path) in ["/root", "/home/user"]
        skel = Path(sysskel) / Path("etc/skel")
        assert path_is_dir(skel)
        assert verbose == inf
        process_skel(
            root=Path(path), skel=skel, count=count, confirm=confirm, verbose=verbose
        )
    else:
        process_skel(
            root=Path("/"), skel=sysskel, count=count, confirm=confirm, verbose=verbose
        )
