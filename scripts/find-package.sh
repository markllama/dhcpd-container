#!/bin/bash
#
# Get information about a package
#
LIBRARY=$1

[ -z "${VERBOSE}" ] || echo "Finding package for library: ${LIBRARY}"

PACKAGE=$(dnf provides ${LIBRARY}  /usr${LIBRARY} 2>/dev/null | head -1 | awk '{print $1}')

echo ${PACKAGE}
