#!/bin/bash
PROXY_PORT=8282

if [[ "$1" == "" ]]; then
    echo "You must provide the namespace to watch on the command line as the first parameter e.g. default"
    exit 1
else
    NAMESPACE=$1
fi

if [[ "$2" == "" ]]; then
    echo "You must provide the name of a ConfigMap to watch on the command line i.e. jenkins-job-map"
    exit 2
else
    CONFIGMAP_TO_WATCH=$2
fi

if [[ "$3" == "" ]]; then
    echo "You must provide an output path for Jenkins jobs on the command line i.e. /var/jenkins_home/jobs"
    exit 3
else
    # can't check for existence/writability yet because the directory doesn't exist until jenkins spins up and starts
    JENKINS_JOB_DIRECTORY=$3
fi

# start kubectl proxy in the background to handle auth etc
kubectl proxy --port=${PROXY_PORT} &
# wait a second for the proxy to start
sleep 1

TEST=$(curl -sS http://localhost:${PROXY_PORT}/api/v1/get/namespaces/${NAMESPACE}/configmaps)
if [ $? -ne 0 ]; then
    echo "There was an error trying to call the Kubernetes API, proxy may not have started"
    exit 255
fi

# start python process to watch kubectl config and generate XML/jobs
while true; do
    python3 -u /kube-jenkins-sidecar/watch.py ${NAMESPACE} ${CONFIGMAP_TO_WATCH} ${JENKINS_JOB_DIRECTORY}
    sleep 2
done

#curl -s http://localhost:${PROXY_PORT}/api/v1/watch/namespaces/${NAMESPACE}/configmaps/${CONFIGMAP_TO_WATCH} | jq -r --stream .

#OUTPUT_JOB_DIR=/var/jenkins_home/jobs
#while FILENAME=$(inotifywait -m -e create "${JOB_DIR}" --format %f .); do
#   echo FILENAME is ${FILENAME} at $(date)
#done

#SERVICE_ACCOUNT_TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
#curl -k -H 'Authorization: Bearer ${SERVICE_ACCOUNT_TOKEN}' https://${KUBERNETES_SERVICE_HOST}:${KUBERNETES_SERVICE_PORT}/api/v1/watch/namespaces/default/configmaps