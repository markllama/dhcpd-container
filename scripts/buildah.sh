#!/bin/bash
#
# Build a container for dhcpd on Fedora
#
set -o errexit

function find_dep_packages() {
    local binary=$1
    ldd ${binary} |
	awk '{print $1}' |
	xargs -I{} find /usr/lib* -name {} |
	xargs -I{} rpm -qf {} |
	sort -u
}

# Create a container
CONTAINER=$(buildah from registry.fedoraproject.org/fedora-minimal:41)

# Mount the container filesystem
MOUNTPOINT=$(buildah mount $CONTAINER)

buildah run $CONTAINER microdnf install -y --releasever 41  --nodocs --setopt install_weak_deps=False dhcp-server
buildah run $CONTAINER microdnf clean all -y --releasever 41

# Cleanup
buildah unmount $CONTAINER

# Start httpd
# buildah config --cmd "httpd -DFOREGROUND" $CONTAINER
buildah config --cmd "/usr/sbin/dhcpd -f -cf /etc/dhcp/dhcpd.conf -user dhcpd -group dhcpd --no-pid" $CONTAINER

# add a volume to include the configuration file
buildah config --volume /etc/dhcp $CONTAINER
buildah config --volume /var/lib/dhcpd $CONTAINER
# add a volume for logs

# open ports for listening
buildah config --port 68/udp --port 69/udp ${CONTAINER}

# Save the container to an image
buildah commit --squash $CONTAINER dhcpd-fedora
