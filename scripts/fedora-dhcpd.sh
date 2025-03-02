#!/bin/bash
# -------------------------------------
# Build a container for dhcpd on Fedora
# -------------------------------------

# To tag and publish the image
# buildah tag localhost/dhcpd-fedora quay.io/markllama/dhcpd-fedora
# buildah push quay.io/markllama/dhcpd-fedora

# Stop on any error 
set -o errexit

function main() {
    # Create a container
    CONTAINER=$(buildah from registry.fedoraproject.org/fedora-minimal:41)

    # Install the DHCP server package and then remove any cached files
    buildah run $CONTAINER dnf install -y --releasever 41  --nodocs --setopt install_weak_deps=False dhcp-server
    buildah run $CONTAINER dnf clean all -y --releasever 41

    # add a volume to include the configuration file
    # Leave the files in the default locations 
    buildah config --volume /etc/dhcp/dhcpd.conf $CONTAINER
    buildah config --volume /var/lib/dhcpd/dhcp.leases $CONTAINER

    # open ports for listening
    buildah config --port 68/udp --port 69/udp ${CONTAINER}

    # Define the startup command
    buildah config --cmd "/usr/sbin/dhcpd -d --no-pid" $CONTAINER

    buildah config --author "Mark Lamourine <markllama@gmail.com>" $CONTAINER
    buildah config --created-by "Mark Lamourine <markllama@gmail.com>" $CONTAINER

    # Save the container to an image
    buildah commit --squash $CONTAINER dhcpd-fedora
}


#
#
#
main $*
