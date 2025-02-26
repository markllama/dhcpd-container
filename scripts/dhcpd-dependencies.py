#!/usr/bin/env python
"""
Find the binaries in a specified RPM and list the required packages
and shared libraries needed for each file.
"""

import argparse
import distro
import functools
import os
import re
import subprocess
import stat
import sys
import urllib.request
import yaml

defaults = {
    'package_name': "dhcp-server",
    'package_dir':  "./minimize/packages",
    'unpack_dir':   "./minimize/unpack"
    
}

def parse_args():

    parser = argparse.ArgumentParser()

    parser.add_argument('--verbose', '-v', type=bool, default=False)
    # parser.add_argument('--check', '-v', type=bool, default=False)

    # operational parameters
    parser.add_argument('--package-dir', default=defaults['package_dir'])
    parser.add_argument('--unpack-dir', default=defaults['unpack_dir'])
    #parser.add_argument('--package-name')

    # parser.add_arguments("--steps")
    
    # Operation Controls    
    parser.add_argument("--pull", type=bool, default=False)
    parser.add_argument("--unpack", type=bool, default=False)

    # Positional arguments
    parser.add_argument("package", default=defaults['package_name'])

    return parser.parse_args()

# --------------------------------------
# YUM repo and RPM management functions
# --------------------------------------
def pull_packages(destdir, package):
    """
    Retrieve an RPM and the dependencies from the default repository
    place the RPMs in the directory indicated.
    """
    
    rpm_cmd = f"/usr/bin/dnf --quiet download --resolve --destdir { destdir } { package }"
    # Create the destination directory 
    not os.path.isdir(destdir) and  os.makedirs(destdir, exist_ok=True)

    # download the package(s)
    result = subprocess.run(rpm_cmd.split(), stdout=subprocess.PIPE)
    

    packages = os.listdir(destdir)

    return packages

def unpack_package(package_file, destdir):
    """
    Unpack an RPM into a directory
    """
    
    convert_command = f"rpm2cpio { package_file }"
    unpack_command = f"cpio -idmu --quiet --directory {destdir}"

    # Create the destination directory if needed
    not os.path.isdir(destdir) and  os.makedirs(destdir, exist_ok=True)

    # rpm2ostree | cpio - Yes Adam, yes.
    convert = subprocess.Popen(convert_command.split(), stdout = subprocess.PIPE)
    unpack = subprocess.Popen(unpack_command.split(), stdin=convert.stdout)
    convert.wait()

def find_lib_package(libname):

    provides_command=f"dnf --quiet provides {libname}"

    response = subprocess.check_output(provides_command.split()).decode('utf-8').split("\n")
    packages = []
    #
    # <pkgname>    : <description>
    # Repo         : <reponame>
    # Matched From : blank
    # Filename     : <filename>
    # <blank>
    pkgname = None
    pkg = {}
    for line in response:
        match = re.match(r"^(\S+\s?\S+)\s+:\s+(.*)$", line)
        if match != None:
            # figure out which
            (key, value) = match.groups(1)
            key = key.lower()
            if key in ['repo', 'filename']:
                pkg[key] = value
            elif key == 'matched from':
                next
            else:
                pkg['name'] = key
                pkg['description'] = value
        else:
            if len(pkg) != 0:
                packages.append(pkg)
                pkg = {}
    
    return packages

# --------------------------------------------------
# Executable file discovery and inspection functions
# --------------------------------------------------
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

def resolve_shared_libraries(root_dir, exe_path):
    """
    Given the root of a tree containing a dynamically linked executable,
    And the normalized path of the executable file,
    Get the list of shared libraries.
    """

    dlink_command = f"ldd { root_dir }{ exe_path}"
    response = subprocess.check_output(['ldd', f"{ root_dir }{ exe_path }"]).decode('utf-8').split("\n")

    # remove leading tabs
    lines = [line.strip().split() for line in response]
    libs = [lib[2] for lib in lines if len(lib) > 2]

    return libs

# ----------------------
# Package name parsing and comparison
# ----------------------
rpm_re = re.compile(r'^(.*)[-:]((\d+)\.(\d+)(\.(\d+))?-(\d+))\.(\S+)\.(\S+)$')
    
def parse_rpm_name(pkg):
    """
    Split a package name into components
    (name,version(major, minor, release, build), distro, arch)

    <name>-<version>.<distro>.<arch>$
    """
    match = rpm_re.match(pkg)

    if match is None:
        return None

    return {
        "name": match.group(1),
        "version": match.group(2),
        "major": int(match.group(3)),
        "minor": int(match.group(4)),
        "release": int(match.group(6)) if match.group(5) is not None else 0,
        "build": int(match.group(7)),
        "distro": match.group(8),
        "arch": match.group(9)
    }

def compare_rpm_name(name1, name2):
    """
    Compare two RPM names.
    If the name, distro or arch don't match, throw an error.
    If they do match, compare the major, minor, release and build
    """

    rpm1 = parse_rpm_name(name1)
    rpm2 = parse_rpm_name(name2)

    if rpm1['name'] != rpm2['name']:
        raise ValueError(f"mismatch package names: {rpm1['name']} != {rpm2['name']}")
    if rpm1['distro'] != rpm2['distro']:
        raise ValueError(f"mismatch package distro: {rpm1['distro']} != {rpm2['distro']}")
    if rpm1['arch'] != rpm2['arch']:
        raise ValueError(f"mismatch package arch: {rpm1['arch']} != {rpm2['arch']}")

    if rpm1['major'] == rpm2['major']:
        if rpm1['minor'] == rpm2['minor']:
            if rpm1['release'] == rpm2['release']:
                return rpm1['build'] - rpm2['build']
            else:
                return rpm1['release'] - rpm2['release']
        else:
            return rpm1['minor'] - rpm2['minor']
    else:
        return rpm1['major'] - rpm2['major']

    raise ValueError("invalid package names")

# ------------------------------------------------------------------------------
# Package Management
# ------------------------------------------------------------------------------
class RPM(object):

    def __init__(self, name):
        self._name = name
        self._url = None
        self._filename = None
        self._dependencies = []

    @property
    def url(self):
        """
        Get download URLs for the package and any dependencies
        """
        if self._url is None:
            rpm_cmd = f"/usr/bin/dnf download --url --urlprotocol https { self._name }"
            result = subprocess.run(rpm_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self._url = result.stdout.decode('utf-8').split("\n")[0]
            self._filename = self._url.split('/')[-1]
            
        return self._url

    @property
    def dependencies(self):
        """
        Get download URLs for the package and any dependencies
        """
        if self._dependencies:
            return self._dependencies
  
        rpm_cmd = f"/usr/bin/dnf download --resolve --url --urlprotocol https { self._name }"
        result = subprocess.run(rpm_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        urls = result.stdout.decode('utf-8').split("\n")[:-1]
        self._dependencies = []
        for url in urls:
            basename = url.split("/")[-1]
            if basename != self._filename:
                self._dependencies.append({"filename": basename, "url": url})
        
        return self._dependencies

    def retrieve(self, destdir, dependencies=True):
        """
        Retrieve an RPM and the dependencies from the default repository
        place the RPMs in the directory indicated.
        """

        # Create the destination directory 
        not os.path.isdir(destdir) and  os.makedirs(destdir, exist_ok=True)

        url = self.url
        path = os.path.join(destdir, self._filename)
        os.path.exists(path) or urllib.request.urlretrieve(url, path)
        
        # download each of the packages if needed
        if dependencies:
            for dep in self.dependencies:
                # get the basename of the URL
                path = os.path.join(destdir, dep['filename'])
                os.path.exists(path) or urllib.request.urlretrieve(dep['url'], path)

# ------------------------------------------------------------------------------
# Executable Binary record
# ------------------------------------------------------------------------------
class DynamicExecutable(object):

    def __init__(self, path):
        self._path = path
        #self._name = basename[path]
        self._name = None
        self._package = None
        self._dependancies = []
        self._libraries = []

    @classmethod
    def find(root_dir):
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


class DynamicLibrary(object):
    
    def __init__(self, name, path=None):
        self._name = name
        self._path = path
        self._package = None
        self._current = None

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":

    steps = ['pull', 'unpack', 'exec', 'dlink', 'paths', 'pkgs', ]
        
    opts = parse_args()

    pkg = RPM(opts.package)
    pkg.retrieve(opts.package_dir)
    #pkg.retrieve(opts.package_dir, unpack=opts.unpack_dir)
    #pkg.unpack(opts.package_dir, opts.unpack_dir)

    sys.exit(1)

    # * pull
    # * unpack
    
    if opts.pull:
        packages = pull_packages(opts.package_dir, opts.package_name)
    else:
        packages = os.listdir(opts.package_dir)

    if opts.unpack:
        for package in packages:
            unpack_package(os.path.join(opts.package_dir, opts.package_name), opts.unpack_dir)



    # Get a list of binary executable files in the unpacked tree
    executables = find_executable(opts.unpack_dir)

    # print(executables)

    # executable
    # {
    #   'name': "",
    #   'path': "",
    #   'package': "",
    #   'libraries': [
    #      # Dynamic library entries
    #      {
    #        'filename': "",
    #        'filepath': "",
    #        'packname': "",
    #        'currvers': ""
    #      },...
    #   ]
    # }

    # Find the shared libraries required by the binary
    shared_libraries = {}
    for exe_name in executables:
        shared_libraries[exe_name] = {
            'libfiles': resolve_shared_libraries(opts.unpack_dir, exe_name),
            'libpaths': {}
        }

    # Find the path of each shared library
    # print(yaml.dump(shared_libraries, indent=2))

    for exe in shared_libraries.keys():

        # Find the package that provides that file
        for lib in shared_libraries[exe]['libfiles']:
            try:
                path = '/usr' + lib
                pkg = find_lib_package(path)
            except subprocess.CalledProcessError:
                path = lib
                pkg = find_lib_package(path)

            shared_libraries[exe]['libpaths'][path] = pkg

        for libfile in shared_libraries[exe]['libpaths'].keys():
            
            # now find the hightest version package
            versions = [ x['name'] for x in shared_libraries[exe]['libpaths'][libfile] ]
            versions.sort(reverse=True)
            #print(f"Library File: { libfile } from package {versions[0]}")

    #
    # Now, for each executable, find the packages needed
    #

    #print(yaml.dump(shared_libraries))

    for exe_path in shared_libraries.keys():
        print(f"- exe path: { exe_path }")
        packages = set()
        for lib_file_path in shared_libraries[exe_path]['libpaths'].keys():
            print(f"  - { lib_file_path }", end="")
            pkg_list = shared_libraries[exe_path]['libpaths'][lib_file_path]
            # Remove duplicates with a set then convert back to list for sort
            pkg_name_list = list(set([pkg['name'] for pkg in pkg_list]))
            # print(f"    { pkg_name_list }")
            pkg_name_list.sort(key=functools.cmp_to_key(compare_rpm_name), reverse=True)
            #print(f"    sorted { pkg_name_list }")
            pkg_name = parse_rpm_name(pkg_name_list[0])['name']

            print(f"  {pkg_name}")
            # remove duplicates with 
            # get a sorted list of the package versions
            packages.add(pkg_name)


    print(sorted(list(packages)))
