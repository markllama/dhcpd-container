#!/bin/bash
# ----------------------------------------
# Build a container for dhcpd from scratch
# ----------------------------------------

# To tag and publish the image
# buildah tag localhost/dhcpd quay.io/markllama/dhcpd
# buildah push quay.io/markllama/dhcpd

# Stop on any error 
set -o errexit

OPT_SPEC='n:r:'

DEFAULT_NAME="dhcpd"
DEFAULT_ROOT="minimize/model/dhcpd"

: NAME="${NAME:=${DEFAULT_NAME}}"
: ROOT="${ROOT:=${DEFAULT_ROOT}}"

function main() {

    parse_args
    
    # Create a container
    CONTAINER=$(buildah from --name $NAME scratch)
    
    MOUNTPOINT=$(buildah mount $CONTAINER)

    (cd ${ROOT} ; find * -type d) | xargs -I{} mkdir -p ${MOUNTPOINT}/${ROOT}/{}
    cp -r $ROOT/* ${MOUNTPOINT}

    mkdir -p ${MOUNTPOINT}/etc/dhcp
    mkdir -p ${MOUNTPOINT}/var/lib/dhcpd

    ln -s usr/lib ${MOUNTPOINT}/lib
    ln -s usr/lib64 ${MOUNTPOINT}/lib64

    
    
    buildah unmount $CONTAINER

    # add a volume to include the configuration file
    # Leave the files in the default locations 
    buildah config --volume /etc/dhcp/dhcpd.conf $CONTAINER
    buildah config --volume /var/lib/dhcpd/dhcp.leases $CONTAINER

    # # open ports for listening
    buildah config --port 68/udp --port 69/udp ${CONTAINER}

    # # Define the startup command
    buildah config --cmd "/usr/sbin/dhcpd -d --no-pid" $CONTAINER

    # # Save the container to an image
    buildah commit --squash $CONTAINER $NAME

    buildah tag localhost/dhcpd quay.io/markllama/dhcpd

}

function parse_args() {
    local opt
    
    while getopts "${OPT_SPEC}" opt; do
	case "${opt}" in
	    n)
		NAME=${OPTARG}
		;;
	    r)
		ROOT=${OPTARG}
		;;
	esac
    done
}

#
#
#
main $*
