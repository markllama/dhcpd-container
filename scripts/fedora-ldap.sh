#!/bin/bash
# -------------------------------------
# Build a container for dhcpd on Fedora
# -------------------------------------

# To tag and publish the image
# buildah tag localhost/dhcpd-fedora quay.io/markllama/dhcpd-fedora
# buildah push quay.io/markllama/dhcpd-fedora

# Stop on any error 
set -o errexit

: AUTHOR=${AUTHOR:="Mark Lamourine <markllama@gmail.com"}

# Create a container
CONTAINER=$(buildah from registry.fedoraproject.org/fedora-minimal)

# Install the DHCP server package and then remove any cached files
buildah run $CONTAINER dnf install -y --nodocs --setopt install_weak_deps=False openldap-servers
buildah run $CONTAINER dnf clean all -y

# # add a volume to include the configuration file
# # Leave the files in the default locations 
# buildah config --volume /etc/dhcp/dhcpd.conf $CONTAINER
# buildah config --volume /var/lib/dhcpd/dhcp.leases $CONTAINER

# # open ports for listening
buildah config --port 389/udp --port 389/tcp ${CONTAINER}
buildah config --port 636/udp --port 636/tcp ${CONTAINER}

# # Define the startup command
# buildah config --cmd "/usr/sbin/dhcpd -d --no-pid" $CONTAINER

buildah config --author "Mark Lamourine <markllama@gmail.com>" $CONTAINER
buildah config --created-by "Mark Lamourine <markllama@gmail.com>" $CONTAINER

# buildah config --annotation description="ISC DHCPD 4.4.3" $CONTAINER
# buildah config --annotation license="MPL-2.0" $CONTAINER

# # Save the container to an image
buildah commit --squash $CONTAINER slapd-fedora

