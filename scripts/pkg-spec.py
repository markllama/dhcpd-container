
def spec(name):
    """
    Split a package name into components
    (name,version(major, minor, release, build), distro, arch)
    
    <name>-<version>.<distro>.<arch>$
    """
    name_re = re.compile(r'^(.*(-(\d+))?)[-:]((\d+)\.(\d+)(\.(\d+))?-(\d+))\.(\S+)\.(\S+)$')
    match = name_re.match(name)

    if match is None:
        print(f"No match for package: {name}")
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
