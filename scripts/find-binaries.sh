#!/bin/bash
#
# Get information about a package
#

: PKG_WORKDIR=${PKG_WORKDIR:=./workdir}
: PKG_UNPACK=${PKG_UNPACK:=${PKG_WORKDIR}/unpack}

PACKAGE=$1
UNPACK_DIR=${PKG_UNPACK}/${PACKAGE}

[ -z "${VERBOSE}" ] || echo "discovering binaries in ${UNPACK_DIR}"

find ${UNPACK_DIR} -type f -perm 755 | sed "s|${UNPACK_DIR}||"
