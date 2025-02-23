#!/bin/bash
#
# Build a container for dhcpd on Fedora
#
set -o errexit

PACKAGE_DIR=./packages
UNPACK_DIR=./unpack

PACKAGES="dhcp-server"

declare -a SHARED_LIBRARIES
declare -a LIBRARY_PATHS
declare -a DEPEND_PACKAGES

function main() {

    mkdir -p ${PACKAGE_DIR}
    
    get_package ${PACKAGE_DIR} $PACKAGES
    unpack_package ${PACKAGE_DIR} ${UNPACK_DIR} $PACKAGES

    binaries=($(find_binaries ${UNPACK_DIR}))
    
    for pkg in ${binaries[@]} ; do
	SHARED_LIBRARIES+=($(shared_libraries ${UNPACK_DIR}/$pkg))
    done

    for lib in ${SHARED_LIBRARIES[@]} ; do
	LIBRARY_PATHS+=($(library_path $lib))
    done

    for path in ${LIBRARY_PATHS[@]} ; do
	DEPEND_PACKAGES+=($(file_package $path))
    done

    IFS=$'\n' SORTED_PACKAGES=($(sort -u <<<"${DEPEND_PACKAGES[*]}"))
    unset IFS

    get_package ${PACKAGE_DIR} ${SORTED_PACKAGES[*]}
    unpack_package ${PACKAGE_DIR} ${UNPACK_DIR} ${SORTED_PACKAGES[*]}

    # now I know the file paths for the binaries and for the dependencies
    # I wonder what will happen if I put them into a container image?

    # I need to create the directory tree and place the binary and the required
    # library files, then copy the files into the tree
}
    
#
#
#
function get_package() {
    local destdir=$1
    shift
    local packages="$*"
    dnf --quiet download --resolve --destdir $destdir $packages
}

function unpack_package() {
    local pkgdir=$1
    local destdir=$2 ; shift 2
    local packages="$*"

    for pkg in ${packages} ; do
	rpm2cpio ${pkgdir}/${pkg}*.rpm | cpio -idmu --quiet --directory ${destdir}
    done
}

function find_binaries() {
    local search_root=$1
    (cd $search_root ; find * -type f -executable)
}

function shared_libraries() {
    local binary=$1
    ldd $binary | awk '{print $1}'
}

function library_path() {
    local library=$1
    if [ -f $library ] ; then
	echo $library
    else
	find /usr/lib64 -type f -name ${library}*
    fi    
}

function file_package() {
    local filename=$1
    rpm --qf "%{NAME}\n" -qf ${filename}
}

# usage: get_package dhcp-server ./RPMS


# function build() {

#
#
#
main $*
