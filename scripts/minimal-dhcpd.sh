#!/bin/bash
# ----------------------------------------
# Build a container for dhcpd from scratch
# ----------------------------------------

# To tag and publish the image
# buildah tag localhost/dhcpd quay.io/markllama/dhcpd
# buildah push quay.io/markllama/dhcpd

# Stop on any error 
set -o errexit

SCRIPT=$0

OPT_SPEC='a:b:c:s:r:'

DEFAULT_SERVICE="dhcpd"
DEFAULT_SOURCE_ROOT="workdir/model"
DEFAULT_AUTHOR="Mark Lamourine <markllama@gmail.com>"
DEFAULT_BUILDER="Mark Lamourine <markllama@gmail.com>"

: SERVICE="${SERVICE:=${DEFAULT_SERVICE}}"
: SOURCE_ROOT="${SOURCE_ROOT:=${DEFAULT_SOURCE_ROOT}/${SERVICE}}"
: AUTHOR="${AUTHOR:=${DEFAULT_AUTHOR}}"
: BUILDER="${BUILDER:=${DEFAULT_BUILDER}}"

function main() {

    parse_args $*

    if [ -z "${BUILDAH_ISOLATION}" -o -z "${CONTAINER_ID}" ] ; then
	# Create a container
	local container=$(buildah from --name $SERVICE scratch)

	if [ -z "${BUILDAH_ISOLATION}" ] ; then
	    # Run the file copy in an unshare environement
	    buildah unshare bash $0 -c ${container} -s ${SOURCE_ROOT}
	else
	    # Aldready in an unshare environment
	    copy_model_tree ${SOURCE_ROOT} ${container}
	fi
	
	# add a volume to include the configuration file
	# Leave the files in the default locations 
	buildah config --volume /etc/dhcp/dhcpd.conf $container
	buildah config --volume /var/lib/dhcpd $container

	# # open ports for listening
	buildah config --port 68/udp --port 69/udp ${container}

	# # Define the startup command
	buildah config --cmd "/usr/sbin/dhcpd -d --no-pid" $container

	buildah config --author "${AUTHOR}" $container
	buildah config --created-by "${BUILDER}" $container
	buildah config --annotation description="ISC DHCPD 4.4.3" $container
	buildah config --annotation license="MPL-2.0" $container

	# # Save the container to an image
	buildah commit --squash $container $SERVICE

	buildah tag localhost/dhcpd quay.io/markllama/dhcpd

	podman rm ${SERVICE}

    else
	# Only the copy needs to happen in an unshare environment
	copy_model_tree ${SOURCE_ROOT} ${CONTAINERb=_ID}
    fi
}

function copy_model_tree() {
    local source_root=$1
    local container_id=$2
    
    # Access the container file space
    local mountpoint=$(buildah mount $container_id)

    # Create the model directory tree
    (cd ${source_root} ; find * -type d) | xargs -I{} mkdir -p ${mountpoint}/{}
    [ -z "${DEBUG}" ] || ls -R ${mountpoint}
    cp -r ${source_root}/* ${mountpoint}
    
    # Create volume mount points
    mkdir -p ${mountpoint}/etc/dhcp
    mkdir -p ${mountpoint}/var/lib/dhcpd

    [ -z ${DEBUG} ] || ls -R ${mountpoint}

    # Release the container file space
    buildah unmount ${container_id}
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
	    c)
		CONTAINER_ID=${OPTARG}
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
