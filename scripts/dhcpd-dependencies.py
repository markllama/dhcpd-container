#!/usr/bin/env python

import subprocess
import stat
import sys
import os

package_dir = "./packages"
package_name = "dhcp-server"

unpack_dir = "./unpack"

def get_packages(destdir, package):
    
    rpm_cmd = f"/usr/bin/dnf --quiet download --resolve --destdir { destdir } { package }"
    # Create the destination directory 
    not os.path.isdir(destdir) and  os.mkdir(destdir)

    # download the package(s)
    subprocess.run(rpm_cmd.split())

    packages = os.listdir(destdir)

    return packages

def unpack_package(package_file, destdir):

    convert_command = f"rpm2cpio { package_file }"
    unpack_command = f"cpio -idmu --quiet --directory {destdir}"

    not os.path.isdir(destdir) and  os.mkdir(destdir)

    convert = subprocess.Popen(convert_command.split(), stdout = subprocess.PIPE)
    unpack = subprocess.Popen(unpack_command.split(), stdin=convert.stdout)
    convert.wait()

def find_binaries(root_dir):

    executables = []
    for (dirpath, dirnames, filenames) in os.walk(root_dir):
        # check each file for permission 'x' in mode string
        # don't follow hidden files or directories
        for f in filenames:
            path = os.path.join(dirpath, f)
            fstat = os.lstat(path)
            try:
                stat.filemode(fstat.st_mode).index('x')
                if not stat.S_ISLNK(fstat.st_mode):
                    executables.append(path)
            except:
                next


    return executables

if __name__ == "__main__":

    packages = get_packages(package_dir, package_name)

    for package in packages:
        unpack_package(os.path.join(package_dir, package), unpack_dir)
    
    binaries = find_binaries(unpack_dir)

    print(binaries)
