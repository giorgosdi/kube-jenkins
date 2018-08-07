#!/usr/bin/env python3
from kubernetes import client, config, watch
# from pprint import pprint
import logging
import os
import shutil
import sys
import yaml

namespace = ""
configmap_to_watch = ""
jenkins_job_directory = ""

if len(sys.argv) < 3:
    print("Usage: watch.py <namespace> <configmap name> <jenkins job output directory>")
    sys.exit(1)
else:
    namespace = sys.argv[1]
    configmap_to_watch = sys.argv[2]
    jenkins_job_directory = sys.argv[3]

# this is mostly needed for local testing
# load_kube_config() will read from ~/.kube/config
# load_incluster_config() uses environment variables/service accounts/token
try:
    config.load_kube_config()
except FileNotFoundError:
    config.load_incluster_config()
v1 = client.CoreV1Api()
v1_batch = client.BatchV1Api()

jenkins_xml_template = """<?xml version='1.1' encoding='UTF-8'?>
<project>
  <description></description>
  <keepDependencies>false</keepDependencies>
  <properties/>
  <scm class="hudson.scm.NullSCM"/>
  <canRoam>true</canRoam>
  <disabled>false</disabled>
  <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
  <blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>
  <triggers/>
  <concurrentBuild>false</concurrentBuild>
  <builders>
    <hudson.tasks.Shell>
      <command>{jenkins_command}</command>
    </hudson.tasks.Shell>
  </builders>
  <publishers/>
  <buildWrappers/>
</project>"""

kubernetes_job_template = """---
kind: Job
apiVersion: batch/v1
metadata:
  name: {job_name}
  namespace: {job_namespace}
spec:
  template:
    metadata:
      labels:
        app: {job_name}
    spec:
      containers:
      - name: {job_name}
        image: 655932586765.dkr.ecr.us-west-2.amazonaws.com/kubernetes-jenkins-job-base
        imagePullPolicy: IfNotPresent
        args: [{job_args}]
        volumeMounts:
        - name: "github-key"
          mountPath: "/etc/github"
  volumes:
  - name: "github-secret"
    secret:
      secretName: "github-key"
    restartPolicy: Never
  backoffLimit: 0
"""


class Job:
    job_directory = ""
    name = ""
    formatted_name = ""
    kube_job_path = ""
    namespace = ""
    url = ""
    branch = ""
    run = ""
    generated_jenkins_command = ""
    generated_jenkins_xml = ""
    generated_kubernetes_job = ""

    def __init__(self, job_dict, job_directory):
        self.job_directory = job_directory
        self.name = job_dict['job'].get('name')
        # self.formatted_name = "{name}".format(job_dict['job'].get('name').replace(' ', '_'))
        # self.kube_job_path = "{name}.yaml".format(.formatted_name)
        self.namespace = job_dict['job'].get('namespace', 'default')
        self.url = job_dict['job'].get('url')
        self.branch = job_dict['job'].get('branch')
        self.run_command = job_dict['job'].get('run_command')
        self.workdir = job_dict['job'].get('workdir')

        self.formatted_name = self.generate_formatted_name()
        self.kube_job_path = self.generate_kube_job_path()

        self.generated_jenkins_xml = self.generate_jenkins_xml()
        self.generated_kubernetes_job = self.generate_kubernetes_job()
        self.generated_jenkins_command = self.generate_jenkins_command()

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def generate_formatted_name(self):
        return self.name.replace(' ', '_')

    def generate_kube_job_path(self):
        return "{name}.yaml".format(name=self.name.replace(' ', '_'))

    def generate_jenkins_command(self):
        return "kubectl apply -f {dir}{sep}{job_path}".format(
            dir=self.job_directory,
            sep=os.sep,
            job_path=self.kube_job_path,
        )

    def generate_jenkins_xml(self):
        # xml_run_command = []
        # if self.workdir:
        #    xml_run_command.append("cd {0}".format(self.workdir))
        # xml_run_command.append(self.run_command)

        logging.debug("Generated Jenkins job spec for '{}'".format(self.name))
        # return jenkins_xml_template.format(run_command="\n".join(xml_run_command))
        return jenkins_xml_template.format(jenkins_command=self.generate_jenkins_command())

    def save_jenkins_xml(self, jenkins_xml):
        # jenkins_xml = self.generated_jenkins_xml
        directory = self.name
        jenkins_job_filename = "{dir}/config.xml".format(dir=directory)
        full_output_path = "{root_path}{sep}{filename}".format(
            root_path=self.job_directory,
            sep=os.sep,
            filename=jenkins_job_filename,
        )
        logging.debug("Jenkins job output path is '{path}'".format(path=full_output_path))

        directory_to_use = "{root_path}{sep}{dir}".format(root_path=self.job_directory, sep=os.sep, dir=directory)
        if not os.path.exists(directory_to_use):
            logging.debug("'{dir}' does not exist, creating it".format(dir=directory_to_use))
            os.makedirs("{root_path}{sep}{dir}".format(root_path=self.job_directory, sep=os.sep, dir=directory))

        with open(full_output_path, 'w') as fp:
            logging.debug("Writing Jenkins XML to '{path}'".format(path=full_output_path))
            fp.write(jenkins_xml)

    def generate_kubernetes_job(self):
        args = "cd {workdir} && {command}".format(workdir=self.workdir, command=self.run_command)
        job_spec = kubernetes_job_template.format(
            job_name=self.formatted_name,
            job_namespace=self.namespace,
            job_args='"{args}"'.format(args=args),
        )
        logging.debug("Generated Kubernetes job spec for '{name}'".format(name=self.formatted_name))
        # print(job_spec)
        return job_spec

    def save_kubernetes_job(self, job_spec):
        # v1_batch.create_namespaced_job(self.namespace, job_spec)
        # directory = self.name
        # jenkins_job_filename = "{dir}/job.xml".format(dir=directory)

        full_output_path = "{root_path}{sep}{filename}".format(
            root_path=self.job_directory,
            sep=os.sep,
            filename=self.kube_job_path,
        )
        logging.debug("Kubernetes job output path is '{path}'".format(path=full_output_path))

        # directory_to_use = "{root_path}/{dir}".format(root_path=self.job_directory, dir=directory)
        # if not os.path.exists(directory_to_use):
        #     logging.debug("'{dir}' does not exist, creating it".format(dir=directory_to_use))
        #     os.makedirs("{root_path}/{dir}".format(root_path=self.job_directory, dir=directory))

        with open(full_output_path, 'w') as fp:
            logging.debug("Writing Kubernetes job to '{path}'".format(path=full_output_path))
            fp.write(job_spec)


def run_cleanup(directory, list_of_current_jobs):
    for subdir, dirs, files in os.walk(directory):
        for file in files:
            # don't process jenkins jobs here
            if file == 'config.xml':
                continue
            # print("file: {file}".format(file=file))
            full_path = "{subdir}{sep}{file}".format(subdir=subdir, sep=os.sep, file=file)

            filename, extension = os.path.splitext(file)
            if filename not in list_of_current_jobs:
                logging.debug("Removing '{path}'".format(path=full_path))
                os.unlink(full_path)
        for directory in dirs:
            # print("dir: {directory}".format(directory=directory))
            full_dir_path = "{subdir}{sep}{directory}".format(subdir=subdir, sep=os.sep, directory=directory)
            if directory not in list_of_current_jobs:
                logging.debug("Recursively removing '{path}'".format(path=full_dir_path))
                shutil.rmtree(full_dir_path)


def parse_job_config(job_config):
    yaml_config = yaml.load(job_config)
    created_jobs = []
    for job_dict in yaml_config:
        # print(Job(job_dict).generated_jenkins_xml)
        this_job = Job(job_dict, jenkins_job_directory)
        this_job.save_jenkins_xml(this_job.generated_jenkins_xml)
        this_job.save_kubernetes_job(this_job.generated_kubernetes_job)
        created_jobs.append(this_job.formatted_name)
    run_cleanup(jenkins_job_directory, created_jobs)


resrc_version = None
w = watch.Watch()
LOG_FORMAT = '%(asctime)-15s %(funcName)s: %(message)s'
logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)

while True:
    if resrc_version is None:
        stream = w.stream(v1.list_namespaced_config_map, namespace)
    else:
        stream = w.stream(v1.list_namespaced_config_map, namespace, resource_version=resrc_version)
    for event in stream:
        if event['raw_object']['metadata']['name'] == configmap_to_watch:
            # print(event)
            resrc_version = event['raw_object']['metadata']['resourceVersion']
            print("{type} ({resourceVersion})".format(type=event['type'], resourceVersion=resrc_version))
            if event['type'] == "ADDED" or event['type'] == "MODIFIED":
                data_structure = event['raw_object']['data']
                if data_structure.get('job-config.yaml'):
                    parse_job_config(data_structure.get('job-config.yaml'))
            if event['type'] == "DELETED":
                run_cleanup(jenkins_job_directory, [])
