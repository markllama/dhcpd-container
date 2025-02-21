#!/bin/bash
#
# Build a container for dhcpd on Fedora
#
set -o errexit

# Create a container
#CONTAINER=$(buildah from registry.fedoraproject.org/fedora:41)
#CONTAINER=$(buildah from scratch)
CONTAINER=$(buildah from registry.fedoraproject.org/fedora-minimal:41)


# Mount the container filesystem
MOUNTPOINT=$(buildah mount $CONTAINER)

# Install a basic filesystem and minimal set of packages, and httpd
#dnf install -y --installroot $MOUNTPOINT  --releasever 41 --nodocs --setopt install_weak_deps=False --use-host-config glibc-minimal-langpack dhcp-server 
#dnf clean all -y --installroot $MOUNTPOINT --releasever 41

#LC_ALL=C dnf install --installroot $MOUNTPOINT --releasever 41 --nodocs --setopt=install_weak_deps=False -q -y --use-host-config glibc-minimal-langpack
#LC_ALL=C dnf --installroot $MOUNTPOINT --releasever 41 clean all

buildah run $CONTAINER microdnf install -y --releasever 41  --nodocs --setopt install_weak_deps=False glibc-minimal-langpack dhcp-server
buildah run $CONTAINER microdnf clean all -y --releasever 41

#buildah run $CONTAINER microdnf install -y --installroot $MOUNTPOINT --releasever 41  --nodocs --setopt install_weak_deps=False glibc-minimal-langpack dhcp-server
#buildah run $CONTAINER microdnf clean all -y --installroot $MOUNTPOINT --releasever 41

# Cleanup
buildah unmount $CONTAINER

# Copy the website
# buildah copy $CONTAINER 'files/*' '/var/www/html/'

# Expose Port 80/tcp
# buildah config --port 80 $CONTAINER

# Start httpd
# buildah config --cmd "httpd -DFOREGROUND" $CONTAINER
buildah config --cmd "bash" $CONTAINER

# Save the container to an image
buildah commit --squash $CONTAINER dhcpd
