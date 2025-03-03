#!/bin/bash
#
# Get information about a package
#

: PKG_WORKDIR=${PKG_WORKDIR:=./workdir}
: PKG_PKGDIR=${PKG_PKGDIR:=${PKG_WORKDIR}/rpms}
: PKG_UNPACK=${PKG_UNPACK:=${PKG_WORKDIR}/unpack}

PACKAGE=$1
ARCH=$(uname -m)
PKG_PATH=$(ls ${PKG_PKGDIR}/${PACKAGE}*${ARCH}.rpm)
UNPACK_DIR=${PKG_UNPACK}/${PACKAGE}

[ -n "${VERBOSE}" ] || echo "unpacking package info: ${PKG_PATH} into ${UNPACK_DIR}"

[ -d ${UNPACK_DIR} ] || mkdir -p ${UNPACK_DIR}
rpm2cpio ${PKG_PATH} | cpio -idmu --quiet --directory ${UNPACK_DIR}
