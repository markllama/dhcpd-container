#!/usr/bin/env python
"""
Find the binaries in a specified RPM and list the required packages
and shared libraries needed for each file.
"""

import argparse
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

#
# 
#
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

# ----------------------
# Package name parsing and comparison
# ----------------------
# ------------------------------------------------------------------------------
# Package Management
# ------------------------------------------------------------------------------
class Package(object):

    def __init__(self, name=None, filename=None):
        self._name = name
        self._filename = filename
        self._releases = None
        self._dependencies = []
        self._url = None

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

    def unpack(self, package_dir, destroot):
        """
        Unpack an RPM into a directory
        """

        destdir = os.path.join(destroot, self._name)
        
        convert_command = f"rpm2cpio { os.path.join(package_dir, self._filename) }"
        unpack_command = f"cpio -idmu --quiet --directory {destdir}"

        # Create the destination directory if needed
        not os.path.isdir(destdir) and  os.makedirs(destdir, exist_ok=True)

        # rpm2ostree | cpio - Yes Adam, yes.
        convert = subprocess.Popen(convert_command.split(), stdout = subprocess.PIPE)
        unpack = subprocess.Popen(unpack_command.split(), stdin=convert.stdout)
        convert.wait()

    @property
    def releases(self):
                
        if self._filename is None:
            raise ValueError(f"no filename defined for package { self._name }")
        
        if self._releases is None:
            # find all the available releases
            try: 
                provides_command=f"dnf --quiet provides {self._filename}"
                response = subprocess.check_output(provides_command.split(), stderr=subprocess.DEVNULL).decode('utf-8').split("\n")
            except subprocess.CalledProcessError as e:
                provides_cmd=f"dnf --quiet provides { self._filename.replace('/usr', '') }"
                response = subprocess.check_output(provides_cmd.split()).decode('utf-8').split("\n")

            # The stdout contains a series of RPM records  like this
            #
            # <pkgname>    : <description>
            # Repo         : <reponame>
            # Matched From : blank
            # Filename     : <filename>
            # <blank>
            entry_re = re.compile(r"^(\S+\s?\S+)\s+:\s+(.*)$")
            releases = []
            name = None
            description = None
            filename = None
            repo = None
            
            for line in response:
                match = entry_re.match(line)
                if match == None:
                    if name is not None:
                        releases.append(Release(name, description, filename, repo))
                        name = None
                        description = None
                        filename = None
                        repo = None
                else:
                    # extract key/value
                    (key, value) = match.groups(1)
                    key = key.lower()
                    if key == 'repo':
                        repo = value
                    elif key == 'filename':
                        filename = value
                    elif key == 'matched from':
                        next
                    else:
                        name = key
                        description = value

            self._releases = sorted(releases, key=functools.cmp_to_key(Release.compare), reverse=True)

        return self._releases

class Release():
    """
    This represents a single release of a package from a yum repo
    """
    def __init__(self, fullname, description=None, filename=None, repo=None):
        self._fullname = fullname
        self._description = description
        self._filename = filename
        self._repo = repo
        self._url = None

    # class variable 
    _release_name_re = re.compile(r'^(.*)[-:]((\d+)\.(\d+)(\.(\d+))?-(\d+))\.(\S+)\.(\S+)$')

    @property
    def fullname(self):
        return self._fullname

    @property
    def spec(self):
        """
        Split a package name into components
        (name,version(major, minor, release, build), distro, arch)

        <name>-<version>.<distro>.<arch>$
        """
        match = self._release_name_re.match(self._fullname)

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

    @property
    def name(self):
        return self.spec['name']

    @property
    def version(self):
        return self.spec['version']

    @property
    def major(self):
        return self.spec['major']

    @property
    def minor(self):
        return self.spec['minor']

    @property
    def release(self):
        return self.spec['release']

    @property
    def build(self):
        return self.spec['build']

    @property
    def distro(self):
        return self.spec['distro']

    @property
    def arch(self):
        return self.spec['arch']

    @staticmethod
    def compare(release1, release2):
        """
        Compare two RPM names.
        If the name, distro or arch don't match, throw an error.
        If they do match, compare the major, minor, release and build
        """

        rpm1 = release1.spec
        rpm2 = release2.spec

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
# Executable Binary record
# ------------------------------------------------------------------------------
class DynamicExecutable(object):

    def __init__(self, name, path=None, package=None):
        self._name = name
        self._path = path
        #self._name = basename[path]
        self._package = package
        self._dependancies = []
        self._libraries = None

    @staticmethod
    def find(root_dir, package=None):
        """
        Return a list of executable files in a file tree.
        """
        exec_paths = []
        for (dirpath, dirnames, filenames) in os.walk(root_dir):
            for f in filenames:
                path = os.path.join(dirpath, f)
                fstat = os.lstat(path)
                try:
                    # check each file for permission 'x' in mode string
                    # raises exception if no match
                    stat.filemode(fstat.st_mode).index('x')

                    # don't include symlinks
                    stat.S_ISLNK(fstat.st_mode) or exec_paths.append(path)
                
                except ValueError:
                    # str.index throws ValueError if match is not found
                    # meaning the file isn't executable
                    next

        # normalize to the OS path (remove the local root dir path
        #return [ path.replace(root_dir,'') for path in executables ]
        execs = []
        for path in exec_paths:
            # create a DynamicExecutable object for each path
            dyn_exec = DynamicExecutable(path.split('/')[-1],
                                         path=path.replace(root_dir, ''),
                                         package=package)
            execs.append(dyn_exec)

        return execs

    def libraries(self, root_dir=None):
        """
        Given the root of a tree containing a dynamically linked executable,
        And the normalized path of the executable file,
        Get the list of shared libraries.
        """

        if self._libraries is None and root_dir is not None:
            #dlink_root = os.path.join(root_dir, self._package, self._path)
            dlink_root = f"{ root_dir }/{ self._package }{ self._path }"
            response = subprocess.check_output(['ldd', dlink_root]).decode('utf-8').split("\n")

            # remove leading tabs
            lines = [line.strip().split() for line in response]

            libpaths = [lib[2] for lib in lines if len(lib) > 2]
            libraries = [DynamicLibrary(path.split('/')[-1], path=path) for path in libpaths]
            self._libraries = libraries
            
        return self._libraries

class DynamicLibrary(object):
    
    def __init__(self, name, path=None):
        self._name = name
        if path:
            self._path = path if path.startswith("/usr") else "/usr" + path
        else:
            self._path = path
        self._package = None
        self._sources = None
        self._current = None


    def package(self, path=None):
        """
        Determine what package(s) provide this library
        """

        if path is not None:
            self._path = path

        if self._package is None:
            self._package = Package(filename=self._path)

        return self._package

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":

    steps = ['pull', 'unpack', 'exec', 'dlink', 'paths', 'pkgs', ]
        
    opts = parse_args()

    pkg = Package(opts.package)

    pkg.retrieve(opts.package_dir)
    pkg.unpack(opts.package_dir, opts.unpack_dir)

    # pkg.executables
    executables = DynamicExecutable.find(os.path.join(opts.unpack_dir,pkg._name), package=pkg._name)

    for exe in executables:
        libraries = exe.libraries(opts.unpack_dir)
        
        for lib in libraries:
            lib_pkg = lib.package()
            releases = lib_pkg.releases

