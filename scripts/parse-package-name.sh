#!/bin/bash

FULL_NAME=$1
ARCH=$(uname -m)
# [[ $FULL_NAME =~ (.*)\.fc41\.${ARCH}$ ]]
[[ $FULL_NAME =~(.+)[-:]([^-]+)-(.+)\.[^.]+\.${ARCH}$ ]]
echo ${BASH_REMATCH[1]} ${BASH_REMATCH[2]} ${BASH_REMATCH[3]}

