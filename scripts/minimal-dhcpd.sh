#!/bin/bash
# ----------------------------------------
# Build a container for dhcpd from scratch
# ----------------------------------------

# To tag and publish the image
# buildah tag localhost/dhcpd quay.io/markllama/dhcpd
# buildah push quay.io/markllama/dhcpd

# Stop on any error 
set -o errexit

OPT_SPEC='a:b:s:r:'

DEFAULT_SERVICE="dhcpd"
DEFAULT_ROOT="minimize/model/dhcpd"
DEFAULT_AUTHOR="Mark Lamourine <markllama@gmail.com>"
DEFAULT_BUILDER="Mark Lamourine <markllama@gmail.com>"

: SERVICE="${SERVICE:=${DEFAULT_SERVICE}}"
: ROOT="${ROOT:=${DEFAULT_ROOT}}"
: AUTHOR="${AUTHOR:=${DEFAULT_AUTHOR}"
: BUILDER="${BUILDER:=${DEFAULT_BUILDER}"

function main() {

    parse_args
    
    # Create a container
    CONTAINER=$(buildah from --name $SERVICE scratch)

    # Access the container file space
    MOUNTPOINT=$(buildah mount $CONTAINER)

    # Create the model directory tree
    (cd ${ROOT} ; find * -type d) | xargs -I{} mkdir -p ${MOUNTPOINT}/${ROOT}/{}
    cp -r $ROOT/* ${MOUNTPOINT}
    # Create system symlinks
    mkdir -p ${MOUNTPOINT}/etc/dhcp
    mkdir -p ${MOUNTPOINT}/var/lib/dhcpd

    # Release the container file space
    buildah unmount $CONTAINER

    # add a volume to include the configuration file
    # Leave the files in the default locations 
    buildah config --volume /etc/dhcp/dhcpd.conf $CONTAINER
    buildah config --volume /var/lib/dhcpd $CONTAINER

    # # open ports for listening
    buildah config --port 68/udp --port 69/udp ${CONTAINER}

    # # Define the startup command
    buildah config --cmd "/usr/sbin/dhcpd --detach --no-pid" $CONTAINER

    buildah config --author "${AUTHOR}" $CONTAINER
    buildah config --created-by "${BUILDER}" $CONTAINER
    buildah config --annotation description="ISC DHCPD 4.4.3" $CONTAINER
    buildah config --annotation license="MPL-2.0" $CONTAINER

    # # Save the container to an image
    buildah commit --squash $CONTAINER $SERVICE

    buildah tag localhost/dhcpd quay.io/markllama/dhcpd

    #podman rm dhcpd
}

function parse_args() {
    local opt
    
    while getopts "${OPT_SPEC}" opt; do
	case "${opt}" in
	    a)
		AUTHOR=${OPTARG}
		;;
	    b)
		BUILDER=${OPTARG}
		;;
	    s)
		SERVICE=${OPTARG}
		;;
	    r)
		ROOT=${OPTARG}
		;;
	esac
    done
}

# == Call main after all functions are defined
main $*
