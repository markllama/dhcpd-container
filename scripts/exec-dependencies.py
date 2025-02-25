#!/usr/bin/env python
#
#
#
import functools
import re
import sys
import yaml

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
        "release": int(match.group(6)) if match.group(6) is not None else 0,
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

if __name__ == "__main__":

    filename = sys.argv[1]

    with open(filename, 'r') as data_file:
        data = yaml.safe_load(data_file)

    # pick omshell first
    #print(f"Keys: {data.keys()}")

    for exe_path in data.keys():
        print(f"- exe path: { exe_path }")
        packages = set()
        for lib_file_path in data[exe_path]['packages'].keys():
            print(f"  - { lib_file_path }", end="")
            pkg_list = data[exe_path]['packages'][lib_file_path]
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
            
    # exe_data = data['/usr/bin/omshell']

    # exe_library_name = list(exe_data['packages'].keys())[0]
    
    # #print(exe_library_name)

    # exe_library = exe_data['packages'][exe_library_name]

    # sorted_pkgs = sorted([pkg['name'] for pkg in exe_library], key=functools.cmp_to_key(compare_rpm_name), reverse=True)
    
    # #print([pkg['name'] for pkg in exe_library])

    # print(sorted_pkgs)

    # pkg_name = parse_rpm_name(sorted_pkgs[0])['name']

    # print(f"Package name: { pkg_name }")

    
