#!/usr/bin/env python

import re
import sys
import yaml

rpm_re = re.compile(r'^(.*)-((\d+)\.(\d+)(\.(\d+))?-(\d+))\.(\S+)\.(\S+)$')
    
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
        "release": int(match.group(5)) if match.group(5) is not None else 0,
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
    (name1, name2) = sys.argv[1:]


    print(f"Comparing { name1 } to { name2 }")

#    rpm1 = parse_rpm_name(name1)
#    rpm2 = parse_rpm_name(name1)

#    print(yaml.dump(rpm1))
#    print(yaml.dump(rpm2))

    print(compare_rpm_name(name1, name2))
