#!/bin/bash -xe
echo "shell-scripts/ovirt_node_cleanup.sh"

DISTRO="{distro}"
CACHE="$PWD"/build

# the die on error function
function die {{
    echo "$1"
    exit 1
}}

#sets the env variables required for the rest
function set_env {{
    export OVIRT_NODE_BASE="$PWD"
    export OVIRT_CACHE_DIR="$CACHE/$DISTRO"
    export OVIRT_LOCAL_REPO=file://"$OVIRT_CACHE_DIR"/ovirt
}}


set_env

clean_failed=false
sudo rm -rf \
    "$CACHE" \
    "$HOME/rpmbuild"
cd "$OVIRT_NODE_BASE"/ovirt-node
make distclean \
    || clean_failed=true
cd "$OVIRT_NODE_BASE"/ovirt-node-iso
make clean \
    || clean_failed=true

if $clean_failed; then
    exit 1
else
    exit 0
fi