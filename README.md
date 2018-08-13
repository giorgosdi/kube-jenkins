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

