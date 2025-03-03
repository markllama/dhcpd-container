#!/bin/bash
#
# Get information about a package
#

: PKG_WORKDIR=${PKG_WORKDIR:=./workdir}
: PKG_PKGDIR=${PKG_PKGDIR:=${PKG_WORKDIR}/rpms}

PACKAGE=$1

[ -z "${VERBOSE}" ] || echo "Getting package info: ${PACKAGE} into ${PKG_PKGDIR}"

# create the package directory if needed
[ -d ${PKG_PKGDIR} ] || mkdir -p ${PKG_PKGDIR}
dnf download --destdir ${PKG_PKGDIR} ${PACKAGE} 
