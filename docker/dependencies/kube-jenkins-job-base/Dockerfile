FROM ubuntu

ENV DEBIAN_FRONTEND "noninteractive"
ENV KUBERNETES_VERSION v1.10.0
ENV HELM_VERSION v2.9.1
ENV SRC_DIR "/src"
ENV AWS_KEY_DIR "/etc/secrets/aws"
ENV GITHUB_KEY_DIR "/etc/secrets/github"
ENV GITHUB_SSH_FINGERPRINT "SHA256:nThbg6kXUpJWGl7E1IGOCspRomTxdCARLviKw6E5SY8"

RUN apt-get -y update && \
    apt-get -y install git curl openssh-client sudo python-pip && \
    rm -rf /var/cache/apt

RUN curl -o /usr/local/bin/kubectl https://storage.googleapis.com/kubernetes-release/release/${KUBERNETES_VERSION}/bin/linux/amd64/kubectl && \
    chmod +x /usr/local/bin/kubectl

RUN curl -sSL https://storage.googleapis.com/kubernetes-helm/helm-${HELM_VERSION}-linux-amd64.tar.gz | tar --strip-components=1 -C /usr/local/bin -xzf - linux-amd64/helm && \
    chmod +x /usr/local/bin/helm

RUN useradd -u 1000 jenkins

RUN mkdir -p ${SRC_DIR} && \
    chown -R jenkins:jenkins ${SRC_DIR} && \
    chmod 755 ${SRC_DIR}

RUN mkdir -p /home/jenkins && \
    chown -R jenkins:jenkins /home/jenkins && \
    chmod 755 /home/jenkins

RUN chown -R jenkins:jenkins /usr/local/bin
RUN echo "jenkins ALL=(ALL:ALL) NOPASSWD:ALL" | sudo EDITOR=tee visudo -f /etc/sudoers.d/jenkins
RUN pip install awscli --upgrade

USER jenkins
RUN helm init --client-only && \
    helm plugin install https://github.com/futuresimple/helm-secrets

RUN sudo rm -f /etc/sudoers.d/jenkins

ADD rootfs/ /

ENTRYPOINT ["/scripts/entrypoint.sh"]