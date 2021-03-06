#!/bin/bash -xe
echo "shell-scripts/system_tests_common.sh"

# Run system tests on ovirt-engine/vdsm
# PARAMETERS
#
# distro
#     Distro to test the deployment on
#
# version
#     Branch currently building
#
# project
#     Project currently building
#
DISTRO="{distro}"
PROJECT="{project}"
VERSION="{version}"

ENGINE_DIST="${{DISTRO}}"
VDSM_DIST="${{DISTRO}}"

OVIRT_CONTRIB="/usr/share/ovirttestenv/"
ENGINE_DIR="${{WORKSPACE:?}}/ovirt-engine"
VDSM_DIR="${{WORKSPACE?}}/vdsm"
VIRT_CONFIG="${{WORKSPACE?}}/scenario.json"
REPOSYNC_YUM_CONFIG="${{OVIRT_CONTRIB}}/config/repos/ovirt-master-snapshot-external.repo"

PREFIX="${{WORKSPACE:?}}/jenkins-deployment-${{BUILD_NUMBER:?}}"

chmod g+x "${{WORKSPACE?}}"

# Create $PREFIX for current run
testenvcli init \
    "${{PREFIX?}}" \
    "${{VIRT_CONFIG?}}"

echo '[INIT_OK] Initialized successfully, need cleanup later'

# Build RPMs
cd "${{PREFIX?}}"
testenvcli ovirt reposetup \
    --reposync-yum-config="${{REPOSYNC_YUM_CONFIG?}}" \
    --engine-dir="${{ENGINE_DIR?}}" \
    --vdsm-dir="${{VDSM_DIR?}}"

# Start VMs
testenvcli start

# Install RPMs
testenvcli ovirt deploy

testenvcli ovirt engine-setup \
    --config="${{OVIRT_CONTRIB?}}/config/answer-files/${{DISTRO}}_${{VERSION}}.conf"

cat > engine-patch.sh << \EOF_patch
su - postgres -c  "psql -d engine -c \
\"INSERT INTO vdc_options (option_value , option_name) VALUES( E'atomic install vdsmc:latest > /dev/null 2>&1 ;docker exec --interactive=true vdsmc \'/container/ovirt-deploy.sh\';','BootstrapCommand');\""
systemctl restart ovirt-engine
EOF_patch

testenvcli shell engine engine-patch.sh

# Start testing
testenvcli ovirt runtest \
    "${{OVIRT_CONTRIB?}}/test_scenarios/bootstrap.py"
testenvcli ovirt collect --output "${{PREFIX?}}/test_logs/post_bootstrap"

testenvcli ovirt runtest \
    "${{OVIRT_CONTRIB?}}/test_scenarios/create_clean_snapshot.py"

testenvcli ovirt runtest \
    "${{OVIRT_CONTRIB?}}/test_scenarios/basic_sanity.py"
testenvcli ovirt collect --output "${{PREFIX?}}/test_logs/post_basic_sanity"
