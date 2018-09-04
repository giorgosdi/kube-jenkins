#!/usr/bin/env python3
import base64
from kubernetes import client, config, watch
import logging
import os
import shutil
import sys
import yaml

configmap_namespace = ""
label_to_watch = ""
jenkins_job_directory = ""

if len(sys.argv) < 3:
    print("Usage: watch.py <namespace> <configmap name> <jenkins job output directory>")
    sys.exit(1)
else:
    configmap_namespace = sys.argv[1]
    label_to_watch = sys.argv[2]
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

# jenkins_xml_template = """<?xml version='1.1' encoding='UTF-8'?>
# <project>
#   <description></description>
#   <keepDependencies>false</keepDependencies>
#   <properties/>
#   <scm class="hudson.scm.NullSCM"/>
#   <canRoam>true</canRoam>
#   <disabled>false</disabled>
#   <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
#   <blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>
#   <triggers/>
#   <concurrentBuild>false</concurrentBuild>
#   <builders>
#     <hudson.tasks.Shell>
#       <command>{jenkins_command}</command>
#     </hudson.tasks.Shell>
#   </builders>
#   <publishers/>
#   <buildWrappers>
#     <hudson.plugins.ansicolor.AnsiColorBuildWrapper plugin="ansicolor@0.5.2">
#       <colorMapName>xterm</colorMapName>
#     </hudson.plugins.ansicolor.AnsiColorBuildWrapper>
#   </buildWrappers>
# </project>"""

jenkins_xml_template = """<?xml version='1.1' encoding='UTF-8'?>
<project>
  <actions/>
  <description></description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <com.coravy.hudson.plugins.github.GithubProjectProperty plugin="github@1.29.2">
      <projectUrl>{git_https_url}</projectUrl>
      <displayName></displayName>
    </com.coravy.hudson.plugins.github.GithubProjectProperty>
  </properties>
  {scm_config_snippet}
  <canRoam>true</canRoam>
  <disabled>false</disabled>
  <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
  <blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>
  <triggers>
    {ghprb_trigger_config}
  </triggers>
  <concurrentBuild>false</concurrentBuild>
  <builders>
    <hudson.tasks.Shell>
      <command>{jenkins_command}</command>
    </hudson.tasks.Shell>
  </builders>
  <publishers/>
  <buildWrappers>
    <hudson.plugins.ansicolor.AnsiColorBuildWrapper plugin="ansicolor@0.5.2">
      <colorMapName>xterm</colorMapName>
    </hudson.plugins.ansicolor.AnsiColorBuildWrapper>
  </buildWrappers>
</project>
"""

ghprb_trigger_template = """
    <org.jenkinsci.plugins.ghprb.GhprbTrigger plugin="ghprb@1.42.0">
      <spec>H/5 * * * *</spec>
      <configVersion>3</configVersion>
      <adminlist>{ghprb_admin_users}</adminlist>
      <allowMembersOfWhitelistedOrgsAsAdmin>false</allowMembersOfWhitelistedOrgsAsAdmin>
      <orgslist>{ghprb_whitelisted_orgs}</orgslist>
      <cron>H/5 * * * *</cron>
      <buildDescTemplate></buildDescTemplate>
      <onlyTriggerPhrase>false</onlyTriggerPhrase>
      <useGitHubHooks>true</useGitHubHooks>
      <permitAll>false</permitAll>
      <whitelist>{ghprb_whitelisted_users}</whitelist>
      <autoCloseFailedPullRequests>false</autoCloseFailedPullRequests>
      <displayBuildErrorsOnDownstreamBuilds>false</displayBuildErrorsOnDownstreamBuilds>
      <whiteListTargetBranches>
        <org.jenkinsci.plugins.ghprb.GhprbBranch>
          <branch></branch>
        </org.jenkinsci.plugins.ghprb.GhprbBranch>
      </whiteListTargetBranches>
      <blackListTargetBranches>
        <org.jenkinsci.plugins.ghprb.GhprbBranch>
          <branch></branch>
        </org.jenkinsci.plugins.ghprb.GhprbBranch>
      </blackListTargetBranches>
      <gitHubAuthId>2e2a66d7-cfa5-42db-ba32-a2a64d89f01d</gitHubAuthId>
      <triggerPhrase></triggerPhrase>
      <skipBuildPhrase>.*\[skip\W+ci\].*</skipBuildPhrase>
      <blackListCommitAuthor></blackListCommitAuthor>
      <blackListLabels></blackListLabels>
      <whiteListLabels></whiteListLabels>
      <includedRegions></includedRegions>
      <excludedRegions></excludedRegions>
      <extensions>
        <org.jenkinsci.plugins.ghprb.extensions.status.GhprbSimpleStatus>
          <commitStatusContext></commitStatusContext>
          <triggeredStatus></triggeredStatus>
          <startedStatus></startedStatus>
          <statusUrl></statusUrl>
          <addTestResults>false</addTestResults>
        </org.jenkinsci.plugins.ghprb.extensions.status.GhprbSimpleStatus>
      </extensions>
    </org.jenkinsci.plugins.ghprb.GhprbTrigger>
"""

git_scm_snippet = """
  <scm class="hudson.plugins.git.GitSCM" plugin="git@3.9.1">
    <configVersion>2</configVersion>
    <userRemoteConfigs>
      <hudson.plugins.git.UserRemoteConfig>
        <name>origin</name>
        <refspec>+refs/pull/*:refs/remotes/origin/pr/*</refspec>
        <url>{git_ssh_url}</url>
        <credentialsId>d989db42-79cf-4222-93e6-3a7301ead9cc</credentialsId>
      </hudson.plugins.git.UserRemoteConfig>
    </userRemoteConfigs>
    <branches>
      <hudson.plugins.git.BranchSpec>
        <name>${{sha1}}</name>
      </hudson.plugins.git.BranchSpec>
    </branches>
    <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
    <submoduleCfg class="list"/>
    <extensions/>
  </scm>
"""

null_scm_snippet = """
  <scm class="hudson.scm.NullSCM"/>
"""

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
      volumes:
      - name: "github-secret"
        secret:
          secretName: "{private_key_secret}"
      - name: "aws-secret"
        secret:
          secretName: "{aws_secret}"
      containers:
      - name: {job_name}
        image: 655932586765.dkr.ecr.us-west-2.amazonaws.com/kube-jenkins-job-base
        imagePullPolicy: IfNotPresent
        args: {job_args}
        volumeMounts:
        - name: "github-secret"
          mountPath: "/etc/secrets/github"
        - name: "aws-secret"
          mountPath: "/etc/secrets/aws"
        env:
        - name: "GIT_URL"
          value: "{git_url}"
        - name: "GIT_BRANCH"
          value: "{git_branch}"
        - name: "GIT_COMMIT"
          value: "%REPLACE_TOKEN_GIT_COMMIT%"
        - name: "SSH_FINGERPRINT"
          value: "{ssh_fingerprint}"
      restartPolicy: Never
      serviceAccountName: {service_account_name}
  backoffLimit: 0
"""


class Job:
    def __init__(self, job_dict, job_directory):
        self.job_directory = job_directory
        self.name = job_dict['job'].get('name')
        self.namespace = job_dict['job'].get('namespace', 'default')
        self.aws_secret = job_dict['job'].get('aws_secret', '')
        self.service_account_name = job_dict['job'].get('service_account_name')

        self.git_url = job_dict['job']['git'].get('url')
        self.git_branch = job_dict['job']['git'].get('branch', '')
        self.private_key_secret = job_dict['job']['git'].get('ssh_secret_ref')
        self.ssh_fingerprint = get_ssh_fingerprint_from_secret(self.private_key_secret, configmap_namespace)

        self.ghprb_enabled = False
        self.ghprb_trigger_config = ""
        self.scm_config_snippet = null_scm_snippet
        ghprb_config_state = job_dict['job'].get('ghprb', {}).get('enabled', '')
        if ghprb_config_state == "true":
            self.ghprb_enabled = True
        if self.ghprb_enabled:
            self.ghprb_admin_users = job_dict['job'].get('ghprb', {}).get('admin_users', '')
            self.ghprb_whitelisted_users = job_dict['job'].get('ghprb', {}).get('whitelisted_users', '')
            self.ghprb_whitelisted_orgs = job_dict['job'].get('ghprb', {}).get('whitelisted_orgs', '')
            self.ghprb_trigger_config = self.generate_ghprb_config()
            self.scm_config_snippet = git_scm_snippet.format(
                git_ssh_url=self.get_github_ssh_url()
            )

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

    def generate_ghprb_config(self):
        return ghprb_trigger_template.format(
            ghprb_admin_users=self.ghprb_admin_users,
            ghprb_whitelisted_users=self.ghprb_whitelisted_users,
            ghprb_whitelisted_orgs=self.ghprb_whitelisted_orgs,
        )

    def generate_jenkins_command(self):
        pre_commands = [
            "#!/bin/bash",
            "echo [jenkins] GIT_COMMIT: \"${GIT_COMMIT}\"",
            "sed -i \"s/%REPLACE_TOKEN_GIT_COMMIT%/${{GIT_COMMIT}}/g\" {dir}{sep}{job_path}".format(
                dir=self.job_directory,
                sep=os.sep,
                job_path=self.kube_job_path,
            ),
            "cat {dir}{sep}{job_path}".format(
                dir=self.job_directory,
                sep=os.sep,
                job_path=self.kube_job_path,
            ),
            "kubectl delete jobs/{job_name} || true".format(
                job_name=self.formatted_name,
            ),
        ]

        run_commands = [
            "kubectl apply -f {dir}{sep}{job_path}".format(
                dir=self.job_directory,
                sep=os.sep,
                job_path=self.kube_job_path,
            )
        ]
        post_commands = [
            "set +e",
            "ATTEMPTS=0",
            "MAX_ATTEMPTS=60",
            "while [ ${ATTEMPTS} -lt 60 ]; do",
            "   ((ATTEMPTS++))",
            "   kubectl logs -f jobs/{job_name} -n {ns}".format(job_name=self.formatted_name, ns=self.namespace),
            "   if [ $? -ne 0 ]; then",
            "       echo \"< Attempt: ${ATTEMPTS}/${MAX_ATTEMPTS}\"",
            "       sleep 3",
            "   else",
            "       break",
            "   fi",
            "done",
            "if [ ${ATTEMPTS} -ge ${MAX_ATTEMPTS} ]; then",
            "    echo '[jenkins] Maximum attempts reached when trying to show logs, showing job description'",
            "    kubectl describe jobs/{job_name}".format(job_name=self.formatted_name),
            "    echo '[jenkins] Exiting with return code 2'",
            "    exit 2",
            "fi",
            "sleep 5 # wait for a short time for job status to update so return status is more accurate",
            "if [[ $(kubectl get jobs/{job_name} -n {ns} -o jsonpath='{{.status.succeeded}}') ]]; then".format(
                job_name=self.formatted_name,
                ns=self.namespace,
            ),
            "    echo '[jenkins] Job succeeded, exiting with return code 0'",
            "    exit 0",
            "elif [[ $(kubectl get jobs/{job_name} -n {ns} -o jsonpath='{{.status.failed}}') ]]; then".format(
                job_name=self.formatted_name,
                ns=self.namespace
            ),
            "    echo '[jenkins] Job failed, showing pod description'",
            "    POD_NAME=$(kubectl get pods --selector job-name={job_name} -o json | jq -r '.items[0].metadata.name')".format(
                job_name=self.formatted_name
            ),
            "    echo \"[jenkins] Pod name: ${POD_NAME}\"",
            "    kubectl describe pod/${POD_NAME}",
            "    echo '[jenkins] Exiting with return code 1'",
            "    exit 1",
            "else",
            "    echo '[jenkins] Unable to determine job status, showing pod description'",
            "    POD_NAME=$(kubectl get pods --selector job-name={job_name} -o json | jq -r '.items[0].metadata.name')".format(
                job_name=self.formatted_name
            ),
            "    echo \"[jenkins] Pod name: ${POD_NAME}\"",
            "    kubectl describe pod/${POD_NAME}",
            "    echo '[jenkins] Exiting with return code 1 for safety'",
            "    exit 1",
            "fi",
        ]
        return "\n".join(pre_commands + run_commands + post_commands)

    def generate_jenkins_xml(self):
        logging.debug("Generated Jenkins job spec for '{name}'".format(name=self.formatted_name))
        return jenkins_xml_template.format(
            jenkins_command=self.generate_jenkins_command(),
            scm_config_snippet=self.scm_config_snippet,
            git_ssh_url=self.get_github_ssh_url(),
            git_https_url=self.get_github_https_url(),
            ghprb_trigger_config=self.ghprb_trigger_config,
        )

    def save_jenkins_xml(self):
        jenkins_xml = self.generated_jenkins_xml
        directory = self.formatted_name
        jenkins_job_filename = "{dir}/config.xml".format(dir=directory)
        full_output_path = "{root_path}{sep}{filename}".format(
            root_path=self.job_directory,
            sep=os.sep,
            filename=jenkins_job_filename,
        )

        directory_to_use = "{root_path}{sep}{dir}".format(root_path=self.job_directory, sep=os.sep, dir=directory)
        if not os.path.exists(directory_to_use):
            logging.debug("'{dir}' does not exist, creating it".format(dir=directory_to_use))
            os.makedirs("{root_path}{sep}{dir}".format(root_path=self.job_directory, sep=os.sep, dir=directory))

        with open(full_output_path, 'w') as fp:
            logging.debug("Writing Jenkins XML for '{name}' to '{path}'".format(
                name=self.formatted_name,
                path=full_output_path,
            ))
            fp.write(jenkins_xml)

    def get_github_https_url(self):
        if 'https://github.com' in self.git_url:
            return self.git_url
        else:
            _, repo_name = self.git_url.split(':')
            repo_name = repo_name.replace('.git', '')
            return "https://github.com/{repo}".format(repo=repo_name)

    def get_github_ssh_url(self):
        if 'git@github.com' in self.git_url:
            return self.git_url
        else:
            part_list = self.git_url.split('/')
            repo_name = '/'.join(part_list[-2:])
            return "git@github.com:{repo}".format(repo=repo_name)

    def generate_kubernetes_job(self):
        arg_list = []
        arg_list.append("cd {workdir}".format(workdir=self.workdir))
        arg_list = arg_list + self.run_command.strip().split("\n")

        job_spec = kubernetes_job_template.format(
            job_name=self.formatted_name,
            job_namespace=self.namespace,
            job_args="{args}".format(args=arg_list),
            git_url=self.git_url,
            git_branch=self.git_branch,
            private_key_secret=self.private_key_secret,
            ssh_fingerprint=self.ssh_fingerprint,
            service_account_name=self.service_account_name,
            aws_secret=self.aws_secret,
        )
        logging.debug("Generated Kubernetes job spec for '{name}'".format(name=self.formatted_name))
        return job_spec

    def save_kubernetes_job(self):
        job_spec = self.generated_kubernetes_job

        full_output_path = "{root_path}{sep}{filename}".format(
            root_path=self.job_directory,
            sep=os.sep,
            filename=self.kube_job_path,
        )

        with open(full_output_path, 'w') as fp:
            logging.debug("Writing Kubernetes job for '{name}' to '{path}'".format(
                name=self.formatted_name,
                path=full_output_path,
            ))
            fp.write(job_spec)


def get_ssh_fingerprint_from_secret(secret_name, secret_namespace):
    secret_object = v1.read_namespaced_secret(secret_name, secret_namespace)
    return base64.b64decode(secret_object.data.get('ssh_fingerprint', '')).decode('utf-8')


def run_cleanup(directory, jobs_to_remove):
    for subdir, dirs, files in os.walk(directory):
        for file in files:
            # don't process jenkins jobs here
            if file == 'config.xml':
                continue
            full_path = "{subdir}{sep}{file}".format(subdir=subdir, sep=os.sep, file=file)

            filename, extension = os.path.splitext(file)
            if filename in jobs_to_remove:
                logging.debug("Removing file '{path}'".format(path=full_path))
                os.unlink(full_path)
        for directory in dirs:
            full_dir_path = "{subdir}{sep}{directory}".format(subdir=subdir, sep=os.sep, directory=directory)
            if directory in jobs_to_remove:
                logging.debug("Recursively removing directory '{path}'".format(path=full_dir_path))
                shutil.rmtree(full_dir_path)


def parse_job_config(job_config):
    yaml_config = yaml.load(job_config)
    return Job(yaml_config[0], jenkins_job_directory)


def save_job(passed_job):
    run_cleanup(jenkins_job_directory, [passed_job.formatted_name])
    passed_job.save_jenkins_xml()
    passed_job.save_kubernetes_job()


resrc_version = None
w = watch.Watch()
LOG_FORMAT = '%(asctime)-15s %(funcName)s: %(message)s'
logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)

while True:
    if resrc_version is None:
        stream = w.stream(v1.list_namespaced_config_map, configmap_namespace)
    else:
        stream = w.stream(v1.list_namespaced_config_map, configmap_namespace, resource_version=resrc_version)
    for event in stream:
        if event['raw_object']['metadata'].get('labels'):
            if event['raw_object']['metadata']['labels'].get(label_to_watch) == "true":
                resrc_version = event['raw_object']['metadata']['resourceVersion']
                print("{type} ({resourceVersion})".format(type=event['type'], resourceVersion=resrc_version))
                if event['type'] == "ADDED" or event['type'] == "MODIFIED":
                    data_structure = event['raw_object']['data']
                    if data_structure.get('job.yaml'):
                        save_job(parse_job_config(data_structure.get('job.yaml')))
                if event['type'] == "DELETED":
                    data_structure = event['raw_object']['data']
                    if data_structure.get('job.yaml'):
                        job = parse_job_config(data_structure.get('job.yaml'))
                        run_cleanup(jenkins_job_directory, [job.formatted_name])
