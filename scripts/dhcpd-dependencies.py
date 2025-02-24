#!/usr/bin/env python
"""
Find the binaries in a specified RPM and list the required packages
and shared libraries needed for each file.
"""
import subprocess
import stat
import sys
import os

package_dir = "./packages"
package_name = "dhcp-server"

unpack_dir = "./unpack"

def get_packages(destdir, package):
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

#def find_shared_libraries(root_dir, exe_path):
    

if __name__ == "__main__":

    packages = get_packages(package_dir, package_name)

    for package in packages:
        unpack_package(os.path.join(package_dir, package), unpack_dir)
    
    binaries = find_executable(unpack_dir)

    print(binaries)
