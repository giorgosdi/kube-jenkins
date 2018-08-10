FROM jenkinsci/jenkins:lts

ENV KUBERNETES_VERSION v1.10.0
ENV HELM_VERSION v2.9.1

USER root

RUN curl -o /usr/local/bin/kubectl https://storage.googleapis.com/kubernetes-release/release/${KUBERNETES_VERSION}/bin/linux/amd64/kubectl && \
    chmod +x /usr/local/bin/kubectl

RUN curl -sSL https://storage.googleapis.com/kubernetes-helm/helm-${HELM_VERSION}-linux-amd64.tar.gz | tar --strip-components=1 -C /usr/local/bin -xzf - linux-amd64/helm && \
    chmod +x /usr/local/bin/helm

USER jenkins