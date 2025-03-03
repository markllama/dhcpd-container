#!/bin/bash
#
# Get information about a package
#

: PKG_WORKDIR=${PKG_WORKDIR:=./workdir}
: PKG_UNPACK=${PKG_UNPACK:=${PKG_WORKDIR}/unpack}

PACKAGE=$1
EXE_NAME=$2

UNPACK_DIR=${PKG_UNPACK}/${PACKAGE}
EXE_PATH=${UNPACK_DIR}${EXE_NAME}

[ -z "${VERBOSE}" ] || echo "discovering shared libraries on ${EXE_PATH}"

# Only lines with filenames and only one file path
ldd ${EXE_PATH} | grep / | sed 's|^[^/]*/|/|;s/ .*$//'
