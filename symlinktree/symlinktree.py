#!/usr/bin/env python3

# pylint: disable=C0111     # docstrings are always outdated and wrong
# pylint: disable=W0511     # todo is encouraged
# pylint: disable=R0902     # too many instance attributes
# pylint: disable=C0302     # too many lines in module
# pylint: disable=C0103     # single letter var names
# pylint: disable=R0911     # too many return statements
# pylint: disable=R0912     # too many branches
# pylint: disable=R0915     # too many statements
# pylint: disable=R0913     # too many arguments
# pylint: disable=R1702     # too many nested blocks
# pylint: disable=R0914     # too many local variables
# pylint: disable=R0903     # too few public methods
# pylint: disable=E1101     # no member for base
# pylint: disable=W0201     # attribute defined outside __init__

import os
import time
from pathlib import Path
from shutil import get_terminal_size
from shutil import move
import click
from kcl.printops import eprint
from kcl.symlinkops import is_broken_symlink
from kcl.symlinkops import is_unbroken_symlink
from kcl.symlinkops import symlink_or_exit
from kcl.dirops import path_is_dir
from getdents import paths
from icecream import ic
ic.configureOutput(includeContext=True)
ic.lineWrapWidth, _ = get_terminal_size((80, 20))

global SKIP_DIRS
SKIP_DIRS = set()


def mkdir_or_exit(folder, confirm, verbose):
    if verbose:
        ic(folder)
    if confirm:
        input("press enter to os.makedirs({})".format(folder))
    try:
        os.makedirs(folder)
    except Exception as e:
        eprint("Exception: %s", e)
        eprint("Unable to os.mkdir(%s). Exiting.", folder)
        quit(1)


def move_path_to_old(path, confirm, verbose):
    path = Path(path)
    timestamp = str(time.time())
    dest = path.with_name(path.name + '._symlinktree_old.' + timestamp)
    if verbose:
        eprint("{} -> {}".format(path, dest))
    if confirm:
        input("press enter to move({}, {})".format(path, dest))
    move(path, dest)


def process_infile(root, skel, infile, confirm, verbose=False):
    assert '._symlinktree_old.' not in infile.as_posix()
    global SKIP_DIRS
    eprint("")
    ic(infile)

    if infile == skel:
        return

    if root == Path('/root'):
        if infile.name == '.ssh':
            return

    if verbose:
        ic(root)
        ic(skel)

    dest_dir = Path(root / infile.relative_to(skel)).parent
    ic(dest_dir)

    possible_symlink_dir = Path(infile.parent / Path('.symlink_dir'))  # walrus!

    if possible_symlink_dir.exists():
        eprint("found .symlink_dir dotfile:", possible_symlink_dir)
        SKIP_DIRS.add(infile.parent)
        ic(SKIP_DIRS)
        assert not dest_dir.is_file()

        if not dest_dir.exists():
            symlink_or_exit(infile.parent, dest_dir, confirm=confirm, verbose=verbose)
            return

        if is_unbroken_symlink(dest_dir):
            assert dest_dir.resolve() == infile.parent
            return

        if is_broken_symlink(dest_dir):
            if is_broken_symlink(infile):
                eprint("infile: {} is a broken symlink, skipping".format(infile))
                return
            if verbose:
                eprint("found broken symlink:", dest_dir)
                quit(1)  # todo

        elif path_is_dir(dest_dir):
            move_path_to_old(dest_dir, confirm=confirm, verbose=verbose)  # might want to just rm broken symlinks
            symlink_or_exit(infile.parent, dest_dir, confirm=confirm, verbose=verbose)
            return

    if is_broken_symlink(infile):   # dont process broken symlinks
        return

    if not infile.is_symlink():         # is_dir() returns true for symlinks to dirs
        if infile.is_dir():             # dont make symlinks to dirs unless .symlink_dir exists
            return

    dest_file = root / infile.relative_to(skel)
    ic(dest_file)
    if is_broken_symlink(dest_file):
        if is_broken_symlink(infile):
            eprint("infile: {} is a broken symlink, skipping".format(infile))
            return
        eprint("found broken symlink at dest_file:", dest_file, "moving it to .old")
        move_path_to_old(dest_file, confirm=confirm, verbose=verbose)
    elif is_unbroken_symlink(dest_file):
        if dest_file.resolve() == infile.resolve():  # must resolve() infile cuz it could also be a symlink
            eprint("skipping pre-existing correctly linked dest file")
            return
        else:
            if verbose:
                eprint("moving incorrectly linked symlink")
                ic(dest_file.resolve())
                ic(infile)
            move_path_to_old(dest_file, confirm=confirm, verbose=verbose)

    if not os.path.islink(dest_file):
        if dest_file.exists():
            eprint("attempting to move pre-existing dest file to make way for symlink dest_file:", dest_file)
            move_path_to_old(dest_file, confirm=confirm, verbose=verbose)

    if not dest_dir.exists():
        eprint("making dest_dir:", dest_dir)
        mkdir_or_exit(dest_dir, confirm=confirm, verbose=verbose)

    symlink_or_exit(infile, dest_file, confirm=confirm, verbose=verbose)


def skip_path(infile, verbose):
    for parent in infile.parents:
        if parent in SKIP_DIRS:
            if verbose:
                eprint("skipping: {} parent {} in SKIP_DIRS:".format(infile, parent))
            return True
    return False


def process_skel(root, skel, count, confirm, verbose=False):
    if verbose:
        ic(root)
        ic(skel)

    for index, infile in enumerate(paths(skel, return_dirs=True, return_files=True, return_symlinks=True)):
        if count:
            if index >= count:
                return
        infile = infile.pathlib
        if not skip_path(infile, verbose=verbose):
            process_infile(root=root, skel=skel, infile=infile, confirm=confirm, verbose=verbose)


@click.command()
@click.argument("sysskel", type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=str, allow_dash=False), nargs=1, required=True)
@click.option("--count", type=int, required=False)
@click.option("--re-apply-skel", type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=str, allow_dash=False), nargs=1, required=False)
@click.option("--verbose", is_flag=True)
@click.option("--confirm", is_flag=True)
def cli(sysskel, count, re_apply_skel, verbose, confirm):
    global SKIP_DIRS

    sysskel = Path(sysskel).resolve()
    assert path_is_dir(sysskel)
    if not os.path.exists(sysskel):
        eprint("sysskel_dir:", sysskel, "does not exist. Exiting.")
        quit(1)

    if re_apply_skel:
        eprint("\n\nre-applying skel")
        path = Path(re_apply_skel)
        assert str(path) in ['/root', '/home/user']
        skel = Path(sysskel) / Path('etc/skel')
        assert path_is_dir(skel)
        process_skel(root=Path(path), skel=skel, count=count, confirm=confirm, verbose=verbose)
    else:
        process_skel(root=Path('/'), skel=sysskel, count=count, confirm=confirm, verbose=verbose)


if __name__ == "__main__":
    cli()
