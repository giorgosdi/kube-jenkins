# kube-jenkins

kubernetes-native CI/CD pipelines using Jenkins as a tool to launch jobs.

**NOTE:** For people familiar with Kubernetes terminology, this is a bit like an ingress controller but for CI/CD jobs
in kubernetes.

## Rationale

Kubernetes is really good at running any workloads in the cluster, including CI/CD workloads. Every CI/CD job should be
a kubernetes job.

Jenkins is good at providing high level CI/CD flows.


### Design overview

There are some key invariants this project focuses on:

#### Jenkins

**Local state**

Jenkins is set up to at any time have no local state it depends on. The pod with jenkins can be deleted at any time and
a new, identical jenkins instance will automatically start up right away.

**Declarative job specification**

All jobs are described as Kubernetes config maps, a Jenkins sidecar container auto-discovers jobs from the cluster and
updates the configuration.

There is no way to configure a Jenkins job via the user interface.

Every job is implemented as a helm chart - jobs are versioned, published and updated using helm flow.

**Logs**

All logs are managed by kubernetes, via existing interfaces. Jenkins should provide a link to the external log storage.

**Access**

Jenkins does not have any access to any infrastructure secrets. It is only authorized to start jobs specified as helm
charts. Logs should be managed by kubernetes.

#### Kubernetes

Kubernetes is responsible for running CI/CD jobs as kubernetes native jobs. It takes care of secret management, resource
allocation, running the jobs and pretty much everything else.


### Example Job ConfigMap

- All ConfigMaps containing jobs that should be processed must have a label with key ```ci-job-spec```, value ```true```
- One job per ConfigMap, any more will be ignored
- Job data YAML must be in a section called ```job.yaml```
- ```ssh_secret_ref``` under the ```git``` section should be the name of a a secret already stored in kubernetes

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: start-helm-test
  namespace: default
  labels: {
    "ci-job-spec": "true"
  }  
data:
  job.yaml: |
    ---
    - job:
        name: "start-helm-test"
        namespace: "default"
        git:
          url: "git@github.com:gravitational/helm-test.git"
          branch: "gravitational/k8s"
          ssh_secret_ref: "github-key"
          ssh_fingerprint: "SHA256:nThbg6kXUpJWGl7E1IGOCspRomTxdCARLviKw6E5SY8"
        aws_secret: "aws-key"        
        service_account_name: "gus-test-jenkins"        
        run_command: |
          kubectl create namespace tiller
          kubectl create serviceaccount --namespace tiller tiller
          kubectl create clusterrolebinding tiller-cluster-rule --clusterrole=cluster-admin --serviceaccount=tiller:tiller
          helm init --tiller-namespace tiller --service-account tiller
          export DECRYPT_CHARTS=false
          kubectl create namespace release-1
          helm-wrapper install --timeout 900 --name release-1 --tiller-namespace tiller helm-test-chart --debug --namespace release-1 -f helm-test/charts/secrets.yaml -f helm-test/secrets.yaml
        workdir: "gravitational/kubernetes/helm"
``` 

Example github secret:

- ```ssh_fingerprint``` is the SSH RSA fingerprint of the git server you're connecting to in SHA256 hash format - see
https://help.github.com/articles/github-s-ssh-key-fingerprints/ for an example (it must be base64-encoded for the secret)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: github-ssh-key
  namespace: default
type: Opaque
data:
  private-key: [base64-encoded SSH private key - e.g. cat ~/.ssh/id_rsa | base64 -w0] 
  ssh_fingerprint: U0hBMjU2Om5UaGJnNmtYVXBKV0dsN0UxSUdPQ3NwUm9tVHhkQ0FSTHZpS3c2RTVTWTg=
```