#!/usr/bin/env python
"""
Find the binaries in a specified RPM and list the required packages
and shared libraries needed for each file.
"""

import argparse
import yaml
import os
import subprocess
import stat
import sys

package_dir = "./packages"
package_name = "dhcp-server"

unpack_dir = "./unpack"

def parse_args():

    parser = argparse.ArgumentParser()

    parser.add_argument("--pull", type=bool, default=False)
    parser.add_argument("--unpack", type=bool, default=False)
    
    return parser.parse_args()

def pull_packages(destdir, package):
    """
    Retrieve an RPM and the dependencies from the default repository
    place the RPMs in the directory indicated.
    """
    
    rpm_cmd = f"/usr/bin/dnf --quiet download --resolve --destdir { destdir } { package }"
    # Create the destination directory 
    not os.path.isdir(destdir) and  os.mkdir(destdir)

    # download the package(s)
    subprocess.run(rpm_cmd.split())

    packages = os.listdir(destdir)

    return packages

def unpack_package(package_file, destdir):
    """
    Unpack an RPM into a directory
    """
    
    convert_command = f"rpm2cpio { package_file }"
    unpack_command = f"cpio -idmu --quiet --directory {destdir}"

    # Create the destination directory if needed
    not os.path.isdir(destdir) and  os.mkdir(destdir)

    # rpm2ostree | cpio - Yes Adam, yes.
    convert = subprocess.Popen(convert_command.split(), stdout = subprocess.PIPE)
    unpack = subprocess.Popen(unpack_command.split(), stdin=convert.stdout)
    convert.wait()

def find_executable(root_dir):
    """
    Return a list of executable files in a file tree.
    """
    executables = []
    for (dirpath, dirnames, filenames) in os.walk(root_dir):
        for f in filenames:
            path = os.path.join(dirpath, f)
            fstat = os.lstat(path)
            try:
                # check each file for permission 'x' in mode string
                # raises exception if no match
                stat.filemode(fstat.st_mode).index('x')

                # don't include symlinks
                stat.S_ISLNK(fstat.st_mode) or executables.append(path)
                
            except ValueError:
                # str.index throws ValueError if match is not found
                # meaning the file isn't executable
                next

    # normalize to the OS path (remove the local root dir path
    return [ path.replace(root_dir,'') for path in executables ]

def find_shared_libraries(root_dir, exe_path):
    """
    Given the root of a tree containing a dynamically linked executable,
    And the normalized path of the executable file,
    Get the list of shared libraries.
    """

    dlink_command = f"ldd { root_dir }{ exe_path}"
    response = subprocess.check_output(['ldd', f"{ root_dir }{ exe_path }"]).decode('utf-8').split("\n")

    # remove leading tabs
    lines = [line.strip().split() for line in response]
    libs = [lib[0] for lib in lines if len(lib) > 0]

    return libs

if __name__ == "__main__":

    steps = ['pull', 'unpack', 'exec', 'libs', 'paths', 'pkgs']
        
    opts = parse_args()

    # * pull
    # * unpack
    
    if opts.pull:
        packages = pull_packages(package_dir, package_name)
    else:
        packages = os.listdir(package_dir)

    if opts.unpack:
        for package in packages:
            unpack_package(os.path.join(package_dir, package), unpack_dir)
    
    executables = find_executable(unpack_dir)

    print(executables)

    # Find the shared libraries required by the binary
    shared_libraries = {}
    for exe_name in executables:
        shared_libraries[exe_name] = {'libfiles': find_shared_libraries(unpack_dir, exe_name)}

    # Find the path of each shared library
    print(yaml.dump(shared_libraries, indent=2))
