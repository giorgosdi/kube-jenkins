#!/bin/bash
set -e

function entrypoint_log() {
    echo "[entrypoint] $*"
}

# error out early if any of our needed variables aren't set
for var in GIT_URL GITHUB_KEY_DIR AWS_KEY_DIR SRC_DIR HOME; do
    if [[ "${!var}" == "" ]]; then
        entrypoint_log "${var} is not set, exiting"
        exit 1
    fi
done

if [ ! -f "${GITHUB_KEY_DIR}/private-key" ]; then
    entrypoint_log "Cannot read private key from '${GITHUB_KEY_DIR}/private-key', make sure the secret is configured properly"
    exit 3
else
    entrypoint_log "Creating '${HOME}/.ssh'"
    mkdir -p ${HOME}/.ssh
    chmod 700 ${HOME}/.ssh
    entrypoint_log "Copying '${GITHUB_KEY_DIR}/private-key' to '${HOME}/.ssh' and fixing permissions"
    cp ${GITHUB_KEY_DIR}/private-key ${HOME}/.ssh/id_rsa
    chmod 600 ${HOME}/.ssh/id_rsa

    # https://help.github.com/articles/github-s-ssh-key-fingerprints/
    if [[ "${SSH_FINGERPRINT}" != "" ]]; then
        # TODO gus: this works for github, will it work for other things?
        DOMAIN=$(echo ${GIT_URL} | awk -F: '{print $1}' | awk -F@ '{print $2}')
        entrypoint_log "Checking SSH fingerprint for '${DOMAIN}'"
        entrypoint_log "Expected result: ${SSH_FINGERPRINT}"
        ssh-keyscan ${DOMAIN} 2>/dev/null > /tmp/scanned_key
        if [ $? -ne 0 ]; then
            entrypoint_log "Error running ssh-keyscan"
            exit 4
        fi
        READ_FINGERPRINT=$(ssh-keygen -lf /tmp/scanned_key | awk '{print $2}')
        if [ $? -ne 0 ]; then
            entrypoint_log "Error running ssh-keygen"
            exit 5
        fi
        rm -f /tmp/scanned_key
        entrypoint_log "Actual result: ${READ_FINGERPRINT}"
        if [[ "${READ_FINGERPRINT}" == "${SSH_FINGERPRINT}" ]]; then
            entrypoint_log "SSH fingerprint matches, writing to '${HOME}/.ssh/known_hosts'"
            ssh-keyscan ${DOMAIN} 2>/dev/null > ${HOME}/.ssh/known_hosts
        else
            entrypoint_log "SSH fingerprint DOES NOT MATCH! This is probably unsafe, exiting"
            exit 6
        fi
    fi
fi

if [ ! -f "${AWS_KEY_DIR}/aws-access-key-id" ]; then
    entrypoint_log "Cannot read AWS access key ID from '${AWS_KEY_DIR}/aws-access-key-id', make sure the secret is configured properly"
    exit 7
elif [ ! -f "${AWS_KEY_DIR}/aws-secret-access-key" ]; then
    entrypoint_log "Cannot read AWS secret access key from '${AWS_KEY_DIR}/aws-secret-access-key', make sure the secret is configured properly"
    exit 8
else
    # AWS_ACCOUNT_ID=""
    # if [ -f "${AWS_KEY_DIR}/aws-account-id" ]; then
    #     AWS_ACCOUNT_ID=$(cat ${AWS_KEY_DIR}/aws-account-id)
    # fi
    entrypoint_log "Creating '${HOME}/.aws'"
    mkdir -p ${HOME}/.aws
    chmod 700 ${HOME}/.aws
    entrypoint_log "Writing '${HOME}/.aws/credentials'"
    cat << EOF > ${HOME}/.aws/credentials
[default]
aws_access_key_id = $(cat ${AWS_KEY_DIR}/aws-access-key-id)
aws_secret_access_key = $(cat ${AWS_KEY_DIR}/aws-secret-access-key)
EOF
    chmod 600 ${HOME}/.aws/credentials
    entrypoint_log "Checking AWS credentials"
    aws sts get-caller-identity
    if [ $? -ne 0 ]; then
        entrypoint_log "AWS credential check failed, exiting"
        exit 9
    fi
fi

if [[ "${GIT_BRANCH}" != "" ]]; then
    entrypoint_log "Cloning branch '${GIT_BRANCH}' of '${GIT_URL}' into '${SRC_DIR}'"
    git clone ${GIT_URL} --branch ${GIT_BRANCH} ${SRC_DIR}
else
    entrypoint_log "No GIT_BRANCH provided"
    entrypoint_log "Cloning '${GIT_URL}' into '${SRC_DIR}'"
    git clone ${GIT_URL} ${SRC_DIR}
fi

# run command from args
entrypoint_log "Working directory: '$(pwd)'"
entrypoint_log "Writing commands to /tmp/run.sh"
echo "cd ${SRC_DIR}" > /tmp/run.sh
echo "$*" >> /tmp/run.sh
chmod +x /tmp/run.sh
entrypoint_log "/tmp/run.sh:"
cat /tmp/run.sh
entrypoint_log "Running /tmp/run.sh"
echo "----------------------------------------------------------"
exec bash -c "/tmp/run.sh"