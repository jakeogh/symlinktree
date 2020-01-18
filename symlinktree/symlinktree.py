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
    ceprint("path:", path)
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
        print("Exception: %s", e)
        print("Unable to os.mkdir(%s). Exiting.", folder)
        os._exit(1)


@click.command()
@click.argument("sysskel", type=click.Path(exists=False, dir_okay=True, path_type=str, allow_dash=False), nargs=1, required=True)
def cli(sysskel):
    sysskel_dir = sysskel
    sysskel_dir = os.path.realpath(sysskel_dir)
    assert path_is_dir(sysskel_dir)

    if not os.path.exists(sysskel_dir):
        print("sysskel_dir:", sysskel_dir, "does not exist. Exiting.")
        os._exit(1)

    #orig_file_list = [os.path.join(path, filename) for path, dirs, files in os.walk(sysskel_dir) for filename in files]
    file_list = files(sysskel_dir)

    skip_list = []
    for infile in file_list:
        skip_current = False
        print("\ninfile:", infile)
        if infile.pathlib.name == '.symlink_dir':
            print("skipping .symlink_dir dotfile")
            continue
        for item in skip_list:
            if str(infile.pathlib).startswith(item):
                print("skip_list skipping:", infile)
                skip_current = True
                break
        if skip_current:
            continue
        if path_is_dir(infile):
            #print("found directory:", infile)
            #print("checking if it contains .symlink_dir")
            if file_exists(infile + '/.symlink_dir'):
                print(".symlink_dir found")
                print("adding", infile, "to skip_list")
                skip_list.append(infile + '/')
            else:
                print("skipping directory:", infile)
                continue

        timestamp = str(time.time())
        dest_dir = '/' + '/'.join(str(infile.pathlib).split('/')[4:-1])
        if is_unbroken_symlink(dest_dir):
            print("dest_dir is a unbroken symlink, checking if it points to the infiles own dir")
            dest_dir_symlink_destination = symlink_destination(dest_dir)
            infile_folder = '/'.join(str(infile.pathlib).split('/')[0:-1])
            print("dest_dir_symlink_destination:", dest_dir_symlink_destination)
            print("infile_folder:", infile_folder)
            try:  #bug papered over, remove the try
                assert not dest_dir_symlink_destination == infile_folder
            except AssertionError:
                continue

        dest_file = '/' + '/'.join(str(infile.pathlib).split('/')[4:])
        print("dest_file:", dest_file)
        #continue
        if is_broken_symlink(dest_file):
            print("found broken symlink at dest_file:", dest_file, "moving it to .old")
            shutil.move(dest_file, dest_file + '.old.' + timestamp)
            #quit(1)

        elif is_unbroken_symlink(dest_file):
            print("skipping pre-existing dest file")
            continue

        if not os.path.islink(dest_file):
            print("attempting to move pre-existing dest file to make way for symlink dest_file:", dest_file)
            try:
                shutil.move(dest_file, dest_file + '.old.' + timestamp)
                #quit(1)
            except Exception as e:
                print(e)
                pass
    ##          print("Problem moving existing file to backup file, exiting")
    ##          os._exit(1)

        if not path_exists(dest_dir):
            print("making dest_dir:", dest_dir)
            mkdir_or_exit(dest_dir)

        symlink_or_exit(infile, dest_file)
    pass


if __name__ == "__main__":
    cli()


# import IPython; IPython.embed()
# import pdb; pdb.set_trace()
# from pudb import set_trace; set_trace(paused=False)#!/usr/bin/env python3
