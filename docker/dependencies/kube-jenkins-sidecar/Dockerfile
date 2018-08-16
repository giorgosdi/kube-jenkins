#FROM quay.io/gravitational/debian-grande@sha256:b4a2291a3b55ce6e71693a28269ee1228f164d887086168974bc967cec54bab3
FROM ubuntu

ENV KUBERNETES_VERSION v1.11.0
ENV DEBIAN_FRONTEND "noninteractive"

RUN apt-get -y update && \
    apt-get -y install curl vim sudo python3 python3-pip jq && \
    rm -rf /var/cache/apt

# jq in debian apt is 1.4.1, we need 1.5
#RUN curl -Lo /usr/local/bin/jq https://github.com/stedolan/jq/releases/download/jq-1.5/jq-linux64 && \
#    chmod +x /usr/local/bin/jq

#ADD https://storage.googleapis.com/kubernetes-release/release/v1.10.0/bin/linux/amd64/kubectl /usr/local/bin/
RUN curl -o /usr/local/bin/kubectl https://storage.googleapis.com/kubernetes-release/release/${KUBERNETES_VERSION}/bin/linux/amd64/kubectl && \
    chmod +x /usr/local/bin/kubectl

RUN useradd -u 1000 jenkins

# TODO remove, this should only be temporary
RUN sed -i 's/Defaults    requiretty/#Defaults    requiretty/g' /etc/sudoers
RUN echo "jenkins ALL=(ALL) NOPASSWD: ALL" | tee -a visudo

# speeds up build
ADD rootfs/kube-jenkins-sidecar/requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

ADD rootfs/ /

USER jenkins

ENTRYPOINT ["/kube-jenkins-sidecar/entrypoint.sh"]