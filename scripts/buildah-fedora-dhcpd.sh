#!/bin/bash
#
# Build a container for dhcpd on Fedora
#
set -o errexit

function main() {
    # Create a container
    CONTAINER=$(buildah from registry.fedoraproject.org/fedora-minimal:41)

    # Mount the container filesystem
    MOUNTPOINT=$(buildah mount $CONTAINER)

    buildah run $CONTAINER dnf install -y --releasever 41  --nodocs --setopt install_weak_deps=False dhcp-server
    buildah run $CONTAINER dnf clean all -y --releasever 41

    # Cleanup
    buildah unmount $CONTAINER

    # add a volume to include the configuration file
    buildah config --volume /etc/dhcp $CONTAINER
    buildah config --volume /var/lib/dhcpd $CONTAINER
    # add a volume for logs

    # open ports for listening
    buildah config --port 68/udp --port 69/udp ${CONTAINER}

    buildah config --cmd "/usr/sbin/dhcpd -d -cf /etc/dhcp/dhcpd.conf -user dhcpd -group dhcpd --no-pid" $CONTAINER

    # Save the container to an image
    buildah commit --squash $CONTAINER dhcpd-fedora

    #buildah tag localhost/dhcpd-fedora quay.io/markllama/dhcpd-fedora

    #buildah push quay.io/markllama/dhcpd-fedora
}


#
#
#
main $*
