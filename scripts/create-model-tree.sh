#!/bin/bash

BINARY=$1
ARCH=$(uname -m)

: WORKDIR_ROOT=${WORKDIR_ROOT:=./workdir}
: PACKAGE_DIR=${PACKAGE_DIR:=${WORKDIR_ROOT}/rpms}
: UNPACK_ROOT=${UNPACK_ROOT:=${WORKDIR_ROOT}/unpack}
: MODEL_ROOT=${MODEL_ROOT:=${WORKDIR_ROOT}/model}

OPT_SPEC="b:dfm:p:u:w:v"

#function parse_args() {
#    echo parsing args
#    while getopts ${OPT_SPEC} as opt ; do
#	case opt in
#	    b)
#	    ;;
#	esac
#    done
#}

function main() {

    # parse_args
    
    # identify daemon package
    local pkg_fullname=$(find_package $BINARY ${ARCH})
    [ -z "${VERBOSE}" ] || echo "package fullname: ${pkg_fullname}" >&2
    local pkg_spec=($(parse_package_name ${pkg_fullname}))
    local pkg_name=${pkg_spec[0]}

    # download daemon package
    pull_package ${pkg_name} ${PACKAGE_DIR} ${ARCH}

    # unpack daemon package
    unpack_package ${pkg_name} ${PACKAGE_DIR} ${UNPACK_ROOT}

    # locate daemon binary within daemon package
    local binary_path=$(find_binaries ${pkg_name} ${UNPACK_ROOT} | grep ${BINARY})
    [ -z "${VERBOSE}" ] || echo "binary path: ${binary_path}" >&2

    # identify required shared libraries
    local libraries=($(find_libraries ${pkg_name} ${binary_path} ${UNPACK_ROOT}))
    [ -z "${DEBUG}" ] || echo "library files: ${libraries[@]}" >&2

    
    # for each shared library
    local library_file
    declare -a library_packages
    declare -A library_records
    for library_file in ${libraries[@]} ; do
	[ -z "${VERBOSE}" ] || echo "processing library ${library_file}" >&2
	
	## identify library package
	local library_package=$(find_library_package ${library_file})
	local lib_pkg_spec=($(parse_package_name ${library_package}))
	local lib_pkg_name=${lib_pkg_spec[0]}
	library_packages+=(${lib_pkg_name})
	library_records[${library_file}]=${lib_pkg_name}
	
	[ -z "${DEBUG}" ] || echo "library package ${library_package}" >&2

	## download library package
	pull_package ${lib_pkg_name} ${PACKAGE_DIR} ${ARCH}

	## unpack library package
	unpack_package ${lib_pkg_name} ${PACKAGE_DIR} ${UNPACK_ROOT}

	## locate library file
	
    done

    # sort and remove duplicates
    IFS=$'\n' library_packages=($(sort -u <<<"${library_packages[@]}")) ; unset IFS
        
    # create model root and create model symlinks
    initialize_model_tree ${MODEL_ROOT}

    ## copy daemon binary
    # all files from 

    ## for each library
    echo "library records: ${library_records[@]}" >&2
    for library_file in "${!library_records[@]}" ; do
     	library_name=${library_records[${library_file}]}
     	[ -z "${DEBUG}" ] || echo "${library_file} : ${library_name}"

	### copy library
     	copy_file ${library_name} $(basename ${library_file}) ${UNPACK_ROOT} ${MODEL_ROOT}
	
    done
}


function parse_package_name() {
    local FULL_NAME=$1
    local ARCH=$(uname -m)
    [[ $FULL_NAME =~ (.+)[-:]([^-]+)-(.+)\.[^.]+\.${ARCH}$ ]]

    local NAME=${BASH_REMATCH[1]}
    local VERS=${BASH_REMATCH[2]}
    local REL=${BASH_REMATCH[3]}

    [[ $NAME =~ ^(.+)(-([[:digit:]]+))$ ]]
    if [ ${#BASH_REMATCH[@]} -ne 0 ] ; then
	NAME=${BASH_REMATCH[1]}
    fi
    # check first for optionl (-([[:digit:]]+))?
    echo ${NAME} ${VERS} ${REL}
}

#
# Get information about a package
#
function find_package() {
    local file_name=$1

    dnf --quiet provides ${file_name}  /usr${file_name} 2>/dev/null | head -1 | awk '{print $1}'
}

function pull_package() {
    local full_name=$1
    local pkg_dir=$2
    local arch=$3

    [ -z "${VERBOSE}" ] || echo "Getting package info: ${full_name} into ${pkg_dir}" >&2

    # create the package directory if needed
    [ -d ${pkg_dir} ] || mkdir -p ${pkg_dir}
    dnf --quiet download --arch ${arch} --destdir ${pkg_dir} ${full_name}
}

#
# Unpack a package into a working directory
#
function unpack_package() {
    local PKG_NAME=$1
    local PKG_ROOT=$2
    local UNPACK_ROOT=$3

    local PKG_PATH=$(ls ${PKG_ROOT}/${PKG_NAME}*.rpm)
    local UNPACK_DIR=${UNPACK_ROOT}/${PKG_NAME}

    [ -z "${DEBUG}" ] || echo "unpacking package info: ${PKG_PATH} into ${UNPACK_DIR}" >&2

    [ -d ${UNPACK_DIR} ] || mkdir -p ${UNPACK_DIR}
    if [ $(ls $UNPACKDIR | wc -l) -eq 0 ] ; then
	rpm2cpio ${PKG_PATH} | cpio -idmu --quiet --directory ${UNPACK_DIR}
    else
	[ -z "${DEBUG}" ] || echo "already unpacked: ${PKG_NAME}"
    fi
}

function find_binaries() {
    local pkg_name=$1
    local unpack_root=$2

    local unpack_dir=${unpack_root}/${pkg_name}

    [ -z "${DEBUG}" ] || echo "discovering binaries in ${unpack_dir}" >&2

    find ${unpack_dir} -type f -perm 755 | sed "s|${unpack_dir}||"
}


function find_libraries() {

    local PACKAGE=$1
    local EXE_NAME=$2

    local UNPACK_DIR=${UNPACK_ROOT}/${PACKAGE}
    local EXE_PATH=${UNPACK_DIR}${EXE_NAME}

    [ -z "${DEBUG}" ] || echo "discovering shared libraries on ${EXE_PATH}" >&2

    # Only lines with filenames and only one file path
    ldd ${EXE_PATH} | grep / | sed 's|^[^/]*/|/|;s/ .*$//' | sort -u
}

function find_library_package() {
    local library_file=$1

    [ -z "${DEBUG}" ] || echo "Finding package for library: ${library_file}" >&2

    local PACKAGE=$(dnf  --quiet provides ${library_file}  /usr${library_file} 2>/dev/null | head -1 | awk '{print $1}')

    echo ${PACKAGE}
}

# ==========================================================================
#
# ==========================================================================

function initialize_model_tree() {
    local model_root=$1

    # create the root directory if needed
    [ -d ${model_root} ] || mkdir -p ${model_root}

    # Create two required symlinks
    for link_dir in lib lib64 ; do
	[ -L ${model_root}/${link_dir} ] || ln -s usr/${link_dir} ${model_root}/${link_dir}
    done
}

function symlink_target() {
    local file_path=$1
    ls -l ${file_path} | sed 's/.*-> //'
}

function copy_file() {
    local pkg_name=$1
    local file_name=$2
    local src_root=$3
    local dst_root=$4

    local file_path=$(cd ${src_root}/${pkg_name} ; find * -name ${file_name})
    local src_file=${src_root}/${pkg_name}/${file_path}
    local dst_file=${dst_root}/${file_path}
    local dst_dir=$(dirname $dst_file)

    [ -z "${DEBUG}" ] || echo "pkg_name: ${pkg_name}"
    [ -z "${DEBUG}" ] || echo "file_name: ${file_name}"
    [ -z "${DEBUG}" ] || echo "src_root: ${src_root}"
    [ -z "${DEBUG}" ] || echo "dst_root: ${dst_root}"

    [ -z "${VERBOSE}" ] || echo "copying file from ${src_file} to ${dst_dir}"

    [ -d ${dst_dir} ] || mkdir -p ${dst_dir}
    
    # if it's a symlink, copy that
    if [ -L $src_file ] ; then
	[ -z "${DEBUG}" ] || echo "$file_name is a symlink"
	local link_target=$(symlink_target ${src_file})
	[ -z "${DEBUG}" ] || echo "$file_name -> $link_target"
	(cd ${dst_dir} ; ln -s ${link_target} ${file_name})
	src_file=$(dirname ${src_root}/${pkg_name}/${file_path})/${link_target}
	[ -z "${DEBUG}" ] || echo "copying file from ${src_file} to ${dst_dir}"
    fi

    # then copy the actual file
    cp $src_file $dst_dir
}

#
#
#
main *
