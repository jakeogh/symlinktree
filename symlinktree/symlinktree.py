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
## pylint: disable=W0703     # catching too general exception

import os
from pathlib import Path
import time
import shutil
import click
from kcl.printops import eprint
from kcl.symlinkops import is_broken_symlink
from kcl.symlinkops import is_unbroken_symlink
#from kcl.symlinkops import symlink_destination
from getdents import files
#from kcl.fileops import file_exists
from kcl.dirops import path_is_dir
from kcl.symlinkops import symlink_or_exit
from icecream import ic
ic.configureOutput(includeContext=True)
from shutil import get_terminal_size
ic.lineWrapWidth, _ = get_terminal_size((80, 20))

global SKIP_DIRS
SKIP_DIRS = set()

def path_exists(path): #gak, misses symlinks
    ic(path)
    if isinstance(path, str): #filter out bool or int to not bit by os.stat(False) or os.stat(0)
        if os.path.lexists(path):
            return True
        else:
            return False
    else:
        raise TypeError('path_exists() rquires a str')


def mkdir_or_exit(folder):
    try:
        os.makedirs(folder)
    except Exception as e:
        eprint("Exception: %s", e)
        eprint("Unable to os.mkdir(%s). Exiting.", folder)
        os._exit(1)


def move_path_to_old(path, verbose):
    path = Path(path)
    timestamp = str(time.time())
    dest = path.with_name(path.name + '.old.' + timestamp)
    if verbose:
        eprint("{} -> {}".format(path, dest))
    shutil.move(path, dest)


def process_infile(root, skel, infile, verbose=False):
    global SKIP_DIRS

    eprint("\ninfile:", infile)
    if verbose:
        ic(root)

    #dest_dir = Path('/' + '/'.join(str(infile).split('/')[4:-1]))
    #ic(dest_dir)
    dest_dir = Path(root / infile.relative_to(skel)).parent
    ic(dest_dir)

    possible_symlink_dir = Path(infile.parent / Path('.symlink_dir'))  # walrus!

    if possible_symlink_dir.exists():
        eprint("found .symlink_dir dotfile:", possible_symlink_dir)
        SKIP_DIRS.add(infile.parent)
        assert not dest_dir.is_file()

        if not dest_dir.exists():
            symlink_or_exit(infile.parent, dest_dir, verbose=verbose)
            return

        if is_unbroken_symlink(dest_dir):
            assert dest_dir.resolve() == infile.parent
            return

        if is_broken_symlink(dest_dir):
            if verbose:
                eprint("found broken symlink:", dest_dir)
                quit(1)  # todo

        elif path_is_dir(dest_dir):
            move_path_to_old(dest_dir, verbose=verbose)  # might want to just rm broken symlinks
            symlink_or_exit(infile.parent, dest_dir, verbose=verbose)
            return

    dest_file = root / infile.relative_to(skel)
    ic(dest_file)
    if is_broken_symlink(dest_file):
        eprint("found broken symlink at dest_file:", dest_file, "moving it to .old")
        move_path_to_old(dest_file, verbose=verbose)
    elif is_unbroken_symlink(dest_file):
        if dest_file.resolve() == infile:
            eprint("skipping pre-existing correctly linked dest file")
            return
        else:
            move_path_to_old(dest_file, verbose=verbose)

    if not os.path.islink(dest_file):
        if dest_file.exists():
            eprint("attempting to move pre-existing dest file to make way for symlink dest_file:", dest_file)
            move_path_to_old(dest_file, verbose=verbose)

    if not path_exists(dest_dir):
        eprint("making dest_dir:", dest_dir)
        mkdir_or_exit(dest_dir)

    symlink_or_exit(infile, dest_file)


def process_skel(root, skel, count, verbose=False):
    if verbose:
        ic(root)
        ic(skel)

    for index, infile in enumerate(files(skel)):
        if count:
            if index >= count:
                return
        infile = infile.pathlib

        if infile.parent in SKIP_DIRS:
            if verbose:
                eprint("skipping, parent in SKIP_DIRS:", infile)
            continue

        process_infile(root=root, skel=skel, infile=infile, verbose=verbose)


@click.command()
@click.argument("sysskel", type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=str, allow_dash=False), nargs=1, required=True)
@click.option("--count", type=int, required=False)
@click.option("--re-apply-skel", type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=str, allow_dash=False), nargs=1, required=False)
@click.option("--verbose", is_flag=True)
def cli(sysskel, count, re_apply_skel, verbose):
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
        process_skel(root=Path(path), skel=skel, count=count, verbose=verbose)
    else:
        process_skel(root=Path('/'), skel=sysskel, count=count, verbose=verbose)


if __name__ == "__main__":
    cli()
