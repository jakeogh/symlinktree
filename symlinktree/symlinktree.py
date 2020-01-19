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
import sys
from pathlib import Path
import time
import shutil
import click
from kcl.printops import ceprint
from kcl.printops import eprint
from kcl.symlinkops import is_broken_symlink
from kcl.symlinkops import is_unbroken_symlink
from kcl.symlinkops import symlink_destination
from getdents import files
from kcl.fileops import file_exists
from kcl.dirops import path_is_dir
from kcl.symlinkops import symlink_or_exit
from icecream import ic
ic.configureOutput(includeContext=True)
from shutil import get_terminal_size
ic.lineWrapWidth, _ = get_terminal_size((80, 20))
#ic.disable()


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


def move_path_to_old(path, verbose=False):
    path = Path(path)
    timestamp = str(time.time())
    dest = path.with_name(path.name + '.old.' + timestamp)
    if verbose:
        eprint("{} -> {}".format(path, dest))
    shutil.move(path, dest)


@click.command()
@click.argument("sysskel", type=click.Path(exists=False, dir_okay=True, path_type=str, allow_dash=False), nargs=1, required=True)
@click.option("--count", type=int, required=False)
@click.option("--re-apply-skel", is_flag=True)
@click.option("--verbose", is_flag=True)
def cli(sysskel, count, re_apply_skel, verbose):
    sysskel_dir = sysskel
    sysskel_dir = os.path.realpath(sysskel_dir)
    assert path_is_dir(sysskel_dir)

    if not os.path.exists(sysskel_dir):
        eprint("sysskel_dir:", sysskel_dir, "does not exist. Exiting.")
        os._exit(1)

    file_list = files(sysskel_dir)

    skip_dirs = set()
    for index, infile in enumerate(file_list):
        if count:
            if index >= count:
                quit(0)
        infile = infile.pathlib

        if infile.parent in skip_dirs:
            if verbose:
                eprint("skipping, parent in skip_dirs:", infile)
            continue

        eprint("\ninfile:", infile)

        dest_dir = Path('/' + '/'.join(str(infile).split('/')[4:-1]))
        ic(dest_dir)

        possible_symlink_dir = Path(infile.parent / Path('.symlink_dir'))  # walrus!

        if possible_symlink_dir.exists():
            eprint("found .symlink_dir dotfile:", possible_symlink_dir)
            skip_dirs.add(infile.parent)
            assert not dest_dir.is_file()

            if not dest_dir.exists():
                symlink_or_exit(infile.parent, dest_dir, verbose=verbose)
                continue

            if is_unbroken_symlink(dest_dir):
                #eprint("dest_dir is a unbroken symlink, checking if it points to the infiles own dir")
                #dest_dir_symlink_destination = symlink_destination(dest_dir)
                #infile_folder = '/'.join(str(infile).split('/')[0:-1])
                #ic(dest_dir_symlink_destination)
                #ic(infile_folder)
                #assert not dest_dir_symlink_destination == infile_folder

                # better:
                assert dest_dir.resolve() == infile.parent
                continue

            if is_broken_symlink(dest_dir):
                if verbose:
                    eprint("found broken symlink:", dest_dir)
                    quit(1)  # todo

            elif path_is_dir(dest_dir):
                move_path_to_old(dest_dir, verbose=verbose)  # might want to just rm broken symlinks
                symlink_or_exit(infile.parent, dest_dir, verbose=verbose)
                continue

        #if path_is_dir(infile):  # never happens
        #    #print("found directory:", infile)
        #    #print("checking if it contains .symlink_dir")
        #    if file_exists(infile + '/.symlink_dir'):
        #        print(".symlink_dir found")
        #        print("adding", infile, "to skip_list")
        #        skip_list.append(infile + '/')
        #    else:
        #        print("skipping directory:", infile)
        #        continue


        dest_file = '/' + '/'.join(str(infile).split('/')[4:])
        ic(dest_file)
        if is_broken_symlink(dest_file):
            eprint("found broken symlink at dest_file:", dest_file, "moving it to .old")
            move_path_to_old(dest_file)
        elif is_unbroken_symlink(dest_file):
            eprint("skipping pre-existing correctly linked dest file")
            continue

        if not os.path.islink(dest_file):
            eprint("attempting to move pre-existing dest file to make way for symlink dest_file:", dest_file)
            try:
                move_path_to_old(dest_file)
            except Exception as e:
                eprint(e)
                eprint("Problem moving existing file to backup file, exiting")
                os._exit(1)

        if not path_exists(dest_dir):
            eprint("making dest_dir:", dest_dir)
            mkdir_or_exit(dest_dir)

        symlink_or_exit(infile, dest_file)

    if re_apply_skel:
        for path in ['/root', '/home/user']:
            skel = Path(sysskel) / Path('etc/skel')
            assert path_is_dir(skel)
            for infile in files(skel):
                ic(infile)
                dest_file = infile.relative_to(skel)
                ic(dest_file)
                pass


if __name__ == "__main__":
    cli()
