#!/usr/bin/env python3
# -*- coding: utf8 -*-


# pylint: disable=missing-docstring               # [C0111] docstrings are always outdated and wrong
# pylint: disable=C0114  #      Missing module docstring (missing-module-docstring)
# pylint: disable=fixme                           # [W0511] todo is encouraged
# pylint: disable=line-too-long                   # [C0301]
# pylint: disable=too-many-instance-attributes    # [R0902]
# pylint: disable=too-many-lines                  # [C0302] too many lines in module
# pylint: disable=invalid-name                    # [C0103] single letter var names, name too descriptive
# pylint: disable=too-many-return-statements      # [R0911]
# pylint: disable=too-many-branches               # [R0912]
# pylint: disable=too-many-statements             # [R0915]
# pylint: disable=too-many-arguments              # [R0913]
# pylint: disable=too-many-nested-blocks          # [R1702]
# pylint: disable=too-many-locals                 # [R0914]
# pylint: disable=too-few-public-methods          # [R0903]
# pylint: disable=no-member                       # [E1101] no member for base
# pylint: disable=attribute-defined-outside-init  # [W0201]
# pylint: disable=too-many-boolean-expressions    # [R0916] in if statement
from __future__ import annotations

import os
import sys
import time
from math import inf
from pathlib import Path
from shutil import move

import click
from asserttool import ic
from clicktool import click_add_options
from clicktool import click_global_options
from clicktool import tv
from eprint import eprint
from getdents import paths
from pathtool import is_broken_symlink
from pathtool import is_unbroken_symlink
from pathtool import make_file_not_immutable  # todo, reset +i
from pathtool import mkdir_or_exit
from pathtool import path_is_dir
from pathtool import symlink_or_exit
from walkup_until_found import walkup_until_found

global SKIP_DIRS
SKIP_DIRS = set()


def move_path_to_old(
    path: Path,
    confirm: bool,
    verbose: bool | int | float = False,
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
    verbose: bool | int | float = False,
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
        ic(root, skel)

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

    try:
        if walkup_until_found(path=infile.parent, name=".symlink_dir", verbose=verbose):
            ic(infile.parent, "has ancestor with .symlink_dir, skipping")
            return
    except FileNotFoundError:
        pass

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
            try:
                move_path_to_old(dest_file, confirm=confirm, verbose=verbose)
            except PermissionError as e:
                ic(e)
                if e.errno == 1:  # "Operation not permitted"
                    make_file_not_immutable(path=dest_file, verbose=verbose)
                    # orig_mode = dest_file.lstat().st_mode
                    # temp_mode = orig_mode & ~stat.UF_IMMUTABLE
                    # os.chattr(dest_file, temp_mode)
                    dest_file.chmod(0o640)
                    move_path_to_old(dest_file, confirm=confirm, verbose=verbose)
                    # os.chattr(dest_file, temp_mode)

    if not dest_dir.exists():
        ic("making dest_dir:", dest_dir)
        mkdir_or_exit(dest_dir, confirm=confirm, verbose=verbose)

    symlink_or_exit(
        target=infile, link_name=dest_file, confirm=confirm, verbose=verbose
    )


def skip_path(
    infile: Path,
    verbose: bool | int | float = False,
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
    verbose: bool | int | float = False,
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
        if verbose == inf:
            ic(_infile)
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
    verbose_inf: bool,
    dict_output: bool,
    confirm: bool,
    verbose: bool | int | float = False,
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
        process_skel(
            root=Path(path), skel=skel, count=count, confirm=confirm, verbose=verbose
        )
    else:
        process_skel(
            root=Path("/"), skel=sysskel, count=count, confirm=confirm, verbose=verbose
        )
