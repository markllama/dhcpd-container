#!/usr/bin/env python
"""
Find the binaries in a specified RPM and list the required packages
and shared libraries needed for each file.

* Retrieve and unpack a copy of the parent package
* Identify binary executables
* For each binary executable
* - Identify shared object libraries
* - Determine file path for each shared object library
* - Determine the provider package for each shared object library
* For each container image
* - Create empty file tree root
* - Copy binary to container file tree
* - For each dynamic library file
*   - Retrieve package file
*   - Unpack package file
*   - Copy shared object library file into container file tree
"""

import argparse
import functools
import os
import re
import shutil
import subprocess
import stat
import sys
import urllib.request
import yaml

defaults = {
    'package_name': "dhcp-server",
    'daemon_file':  "dhcpd",
    'package_dir':  "./minimize/packages",
    'unpack_dir':   "./minimize/unpack",
    'model_dir': "./minimize/model"
}

#
# 
#
def parse_args():

    parser = argparse.ArgumentParser()

    parser.add_argument('--verbose', '-v', action=argparse.BooleanOptionalAction)
    parser.add_argument('--debug', '-d', action=argparse.BooleanOptionalAction)
    
    parser.add_argument('--manifest', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--resolve', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--model', action=argparse.BooleanOptionalAction, default=True)
    
    # parser.add_argument('--check', '-v', type=bool, default=False)

    # operational parameters
    parser.add_argument('--package-dir', default=defaults['package_dir'])
    parser.add_argument('--unpack-dir', default=defaults['unpack_dir'])
    parser.add_argument('--model-dir', default=defaults['model_dir'])

    parser.add_argument("--daemon-file", default=defaults['daemon_file'])

    # Positional arguments
    parser.add_argument("package", default=defaults['package_name'])

    return parser.parse_args()

# ----------------------
# Package name parsing and comparison
# ----------------------
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

    @property
    def name(self):
        return self._name

    @property
    def path(self):
        return self._path

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
        execs = {}
        for path in exec_paths:
            # create a DynamicExecutable object for each path
            dyn_exec = DynamicExecutable(path.split('/')[-1],
                                         path=path.replace(root_dir, ''),
                                         package=package)
            execs[dyn_exec._name] = dyn_exec

        return execs

    def libraries(self, root_dir=None):
        """
        Given the root of a tree containing a dynamically linked executable,
        And the normalized path of the executable file,
        Get the list of shared libraries.
        """
	#       linux-vdso.so.1 (0x0000ffff9e2ac000)
        # 	libc.so.6 => /lib64/libc.so.6 (0x0000ffff9db40000)
	#       /lib/ld-linux-aarch64.so.1 (0x0000ffff9e270000)
        ldd_re = re.compile(r"^(\s*\S+\s=>)?\s+(/\S+)\s+\S+$")
        
        if self._libraries is None and root_dir is not None:
            #dlink_root = os.path.join(root_dir, self._package, self._path)
            dlink_root = f"{ root_dir }/{ self._package }{ self._path }"
            response = subprocess.check_output(['ldd', dlink_root]).decode('utf-8').split("\n")

            libpaths = []
            for line in response:
                match = ldd_re.match(line)
                if match is not None:
                    libpath = match.group(2)
                    libpaths.append(libpath)

             # remove leading tabs            
#            lines = [line.strip().split() for line in response]
#            libpaths = [lib[2] for lib in lines if len(lib) > 2]

            libraries = [DynamicLibrary(path.split('/')[-1], path=path) for path in libpaths]

            self._libraries = libraries
            
        return self._libraries

    def resolve(self, root_dir, verbose=False):
        """
        Find all of the libraries and their packages
        """
        for lib in self.libraries(root_dir):
            verbose and print(f"finding releases for lib: {lib.name}")
            lib.package.releases()


    def model(self, package_dir, unpack_dir, model_dir, follow_symlinks=False, verbose=False):
        """
        Build a model file tree for a container image for the daemon.

        - download the RPM file
        - unpack the RPM file
        - create the root directory
        - place the binary file in the tree
        - for each library
        -   * fetch the package
            * unpack the package
            * copy the file
        """
        
        dst_root = f"{ model_dir }/{self._name}"

        verbose and print(f"initializing model root: {dst_root}")
        
        os.makedirs(dst_root, exist_ok=True)
        os.makedirs(f"{dst_root}/usr/lib", exist_ok=True)
        os.symlink("usr/lib", f"{dst_root}/lib", target_is_directory=True) 
        os.makedirs(f"{dst_root}/usr/lib64", exist_ok=True)
        os.symlink("usr/lib64", f"{dst_root}/lib64", target_is_directory=True) 

        pkg = Package(self._package)
        verbose and print(f"preparing package: {self._package}")
        # Get the daemon binary first
        pkg.retrieve(package_dir)
        pkg.unpack(package_dir, unpack_dir)

        src = f"{unpack_dir}/{pkg._name}/{self._path}"
        dst = f"{dst_root}/{self._path}"
        # copy the binary
        verbose and print(f"placing exe file: {src} => {dst}")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(src, dst, follow_symlinks=follow_symlinks)

        # for each shared library:
        # - retrieve
        # - unpack
        # - mkdir
        # - copy
        for lib in self.libraries():
            verbose and print(f"preparing library: {lib.name}")
            lib._package.retrieve(package_dir)
            lib._package.unpack(package_dir, unpack_dir)

            # mkdir
            # copy
            filename = lib._package._releases[0]._filename
            src = f"{unpack_dir}/{lib._package.name}{filename}"
            dst = f"{dst_root}{filename}"
            verbose and print(f"placing lib file: {src} => {dst}")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst, follow_symlinks=False)

            # If the copied file is a symlink
            if stat.S_ISLNK(os.lstat(dst).st_mode):
                # get the destination and copy that too
                link_value = os.readlink(src)
                src=f"{os.path.dirname(src)}/{link_value}"
                dst=f"{os.path.dirname(dst)}/{link_value}"
                verbose and print(f"placing link target: {src} => {dst}")
                shutil.copy(src, dst, follow_symlinks=follow_symlinks)

    def manifest(self):
        """
        Write a JSON manifest of the files and packages included in the container
        """

        # executable:
        #   package
        #
        #   libraries
        manifest = {
            'name': self.name,
            'path': self.path,
            'package': self._package,
            'libraries': [
                {
                    'path': lib.path,
                    'package': lib.package.latest.name,
                    'version': lib.package.latest.version
                }
                for lib in self._libraries]
        }

        return manifest

class DynamicLibrary(object):
    
    def __init__(self, name, path=None):
        self._name = name
        if path:
            self._path = path if path.startswith("/usr") else "/usr" + path
        else:
            self._path = path
        self._package = None
        self._sources = None
#        self._current = None

    @property
    def name(self):
        return self._name

    @property
    def path(self):
        return self._path

    @property
    def package(self, path=None):
        """
        Determine what package(s) provide this library
        """

        if path is not None:
            self._path = path

        if self._package is None:
            self._package = Package(filename=self._path)

        return self._package


    def retrieve_package(self, path=None):
        self._package.retrieve(path)


# ------------------------------------------------------------------------------
# Package Management
# ------------------------------------------------------------------------------
class Package():

    def __init__(self, name=None, filename=None, url=None):
        self._name = name
        self._filename = filename
        self._executables = None
        self._releases = None
        self._dependencies = []
        self._url = url

    @property
    def name(self):
        if self._name is None:
            if self._filename is not None:
                self.releases()
        return self._name

    @property
    def latest(self):
        """
        Return the package name and version of the latest release
        """
        return self._releases[0]
        
    @property
    def url(self):
        """
        Get download URLs for the package and any dependencies
        """
        if self._url is None:
            search = self._filename if self._filename is not None else self._name
            rpm_cmd = f"/usr/bin/dnf download --url --urlprotocol https { search }"
            result = subprocess.run(rpm_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self._url = result.stdout.decode('utf-8').split("\n")[0]
            self._filename = self._url.split('/')[-1]

        return self._url

    def executables(self, unpack_dir):
        if self._executables == None:
            self._executables = DynamicExecutable.find(
                os.path.join(unpack_dir,self._name),
                package=self._name
            )

        return self._executables

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
                self._dependencies.append(Package(filename=basename, url=url))
        
        return self._dependencies

    def retrieve(self, destdir, dependencies=True):
        """
        Retrieve an RPM and the dependencies from the default repository
        place the RPMs in the directory indicated.
        """

        # Create the destination directory 
        not os.path.isdir(destdir) and os.makedirs(destdir, exist_ok=True)

        url = self.url
        path = f"{ destdir }/{ self._filename }"

        os.path.exists(path) or urllib.request.urlretrieve(url, path)
        
        # download each of the packages if needed
        if dependencies:
            for dep in self.dependencies:
                # get the basename of the URL
                path = os.path.join(destdir, dep._filename)
                os.path.exists(path) or urllib.request.urlretrieve(dep.url, path)

    def unpack(self, package_dir, destroot, force=False):
        """
        Unpack an RPM into a directory
        """
        destdir = os.path.join(destroot, self._name)
        
        convert_command = f"rpm2cpio { os.path.join(package_dir, self._filename) }"
        unpack_command = f"cpio -idmu --quiet --directory {destdir}"

        # Create the destination directory if needed
        not os.path.isdir(destdir) and os.makedirs(destdir, exist_ok=True)

        # only unpack if the destdir is empty or forced 
        if force == True or len(os.listdir(destdir)) == 0:
            # rpm2ostree | cpio - Yes Adam, yes.
            convert = subprocess.Popen(convert_command.split(), stdout = subprocess.PIPE)
            unpack = subprocess.Popen(unpack_command.split(), stdin=convert.stdout)
            convert.wait()

    def releases(self):
        """
        """
        if self._filename is None:
            raise ValueError(f"no filename defined for package { self._name }")
        
        if self._releases is None:
            # find all the available releases
            try: 
                provides_command=f"dnf --quiet provides {self._filename}"
                response = subprocess.check_output(provides_command.split(), stderr=subprocess.DEVNULL).decode('utf-8').split("\n")
            except subprocess.CalledProcessError as e:
                shortname = self._filename.replace('/usr', '')
                provides_cmd=f"dnf --quiet provides { shortname }"
                response = subprocess.check_output(provides_cmd.split()).decode('utf-8').split("\n")
                self._filename = shortname

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

        self._name = self._releases[0].name
        self._filename = self._releases[0]._filename

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


# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
        
    opts = parse_args()

    # Identify and pull a copy of the service deaemon package
    opts.verbose and print(f"Processings package: {opts.package}")
    pkg = Package(opts.package)

    opts.verbose and print(f"Retrieving package: {opts.package}")
    pkg.retrieve(opts.package_dir)

    opts.verbose and print(f"Unpacking package: {opts.package}")
    pkg.unpack(opts.package_dir, opts.unpack_dir)

    # Find the executable files in the package file tree
    opts.verbose and print(f"Finding exe binaries in : {opts.package}")
    executables = pkg.executables(opts.unpack_dir)
    opts.verbose and print(f"{list(executables.keys())}")

    # Select the binary to package
    opts.verbose and print(f"Processing exe: {opts.daemon_file}")
    daemon_exe = executables[opts.daemon_file]

    # Find all shared libraries and their packages
    if opts.resolve:
        opts.verbose and print(f"Processing shared libraries for {daemon_exe.name}")
        daemon_exe.resolve(opts.unpack_dir, verbose=opts.verbose)

    # Create a file tree for the daemon container
    if opts.model:
        opts.verbose and print(f"Creating model for {daemon_exe.name}")
        daemon_exe.model(opts.package_dir, opts.unpack_dir, opts.model_dir, verbose=opts.verbose)

    # Create and print the package manifest
    opts.manifest and print(yaml.dump(daemon_exe.manifest()))
