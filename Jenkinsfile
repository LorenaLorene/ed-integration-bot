// vim: set ft=groovy ts=4 sw=4 et:

def getImageTag = { String APP_NAME, String BRANCH_NAME ->
    // branch names for develop and master will be named 'latest' and 'stable'
    switch (BRANCH_NAME) {
        case ~/^master$/:
            return 'latest'
        case ~/^support\/.*/:
            return BRANCH_NAME.replace('support/', '')
        default:
            // all other branches get a hashed namespace
            hash = sh(
                script: "echo ${APP_NAME}-${BRANCH_NAME} | md5sum | cut -c 1-8",
                returnStdout: true
            ).trim()
            return hash
    }
}

//TODO(Radek): Use Makefile in stages to make Jenkinsfile repository independent
pipeline {
    agent { label('python') }  //TODO(Jorge): Get and agent that has make
    options {
        timestamps()
        disableConcurrentBuilds()  // only allow one build per Git Branch at any moment in time
    }
    environment {
        // OPENSHIFT_CLUSTER_FQDN variable listed in this Jenkinsfile is a GLOBAL ENV VAR defined in the Jenkins server.

        APP_NAME = "interbot"
        OPENSHIFT_PROJECT = 'elucidata-toms-build' // name of the Openshift project where this 'app' will be deployed to.

        IMAGE_TAG = getImageTag(APP_NAME, BRANCH_NAME)

        // set any application variables you need here

        DEBUG=1
        ALLOWED_HOSTS='*'
        CONFIG_URL = 'http://config-latest.elucidata-toms-build.svc:8080'
        GENOMIC_RECORD_URL = 'http://genomicrecord-latest.elucidata-toms-build.svc:8080'

        POD_NAME_FILE="POD_${GIT_COMMIT}.tmp"

        JENKINS_CRED_EXTERNAL_DOCKER_REGISTRY_PUSH_SECRET = 'art-nonprod-servac1'
        JENKINS_CRED_GITHUB_ELUCIDATA_LOGIN = 'github-elucidata-user'
        JENKINS_CRED_GITHUB_ELUCIDATA_PRIVATE_KEY = 'microservice-library-pip-install-id-rsa'
        EXTERNAL_DOCKER_REGISTRY = "${EXTERNAL_DOCKER_REGISTRY}".replace('https://', '')

        TAGGED_APP_NAME = "${APP_NAME}-${IMAGE_TAG}".replace('.', '-')
        SOURCES_ROOT="."
        VENV_DIR='.venv-tests'
        KEEP_COVERAGE_FILE=1
    }

    stages {
        stage('setup') {
            steps {
                echo "Set Openshift project"
                sh "oc project ${OPENSHIFT_PROJECT}"

                echo "Remove stale files and folders"
                sh "rm -rf ${SOURCES_ROOT}/cover ${SOURCES_ROOT}/.mypy_cache ${VENV_DIR} ${SOURCES_ROOT}/.coverage"

                echo "Create virtualenv"
                sh "virtualenv ${VENV_DIR}"

                echo "Backup current private SSH key"
                sh "mkdir -p ~/.ssh"
                sh "chmod 700 ~/.ssh"
                sh "mv ~/.ssh/id_rsa ~/.ssh/id_rsa.old || true"

                echo "Add temporary private SSH key for pip installs"
                withCredentials([
                    file(credentialsId: "${JENKINS_CRED_GITHUB_ELUCIDATA_PRIVATE_KEY}", variable: 'SSH_ID_RSA')]
                ) {
                    sh "cp ${SSH_ID_RSA} ~/.ssh/id_rsa"
                }

                sh "chmod 600 ~/.ssh/id_rsa"
                sh "cp ~/.ssh/id_rsa ${SOURCES_ROOT}/id_rsa"  // Required for docker image build

                echo "Authorize github.com if not already"
                sh '''
                grep -q \"^github.com ssh-rsa \" ~/.ssh/known_hosts \
                    || ssh-keyscan -t rsa github.com >> ~/.ssh/known_hosts
                '''


                echo "Install all pip requirements"
                retry(3) {
                    sh "${VENV_DIR}/bin/pip install -r ${SOURCES_ROOT}/requirements/requirements_dev.txt"
                }
            }

            post {
                always {
                    echo "Remove temporary private SSH key"
                    sh "mv ~/.ssh/id_rsa.old ~/.ssh/id_rsa || rm -f ~/.ssh/id_rsa"
                }
            }
        }

        stage('run all tests') {
            parallel {
                stage('linter') {
                   steps {
                     echo "pass type checks"
                     sh '''
                         source ${VENV_DIR}/bin/activate
                         cd integration_bot
                         pylint --load-plugins pylint_django integration_bot automation
                     '''
                   }
                }
            }
        }

        stage('build and publish docker image to external registry') {
            when {
                expression { BRANCH_NAME.startsWith('support/')  || BRANCH_NAME == 'master'}
            }
            steps {
                echo 'Building and publishing docker image to nexus.'

                    sh '''
                        oc get bc/ext-registry-${TAGGED_APP_NAME} \
                            || oc new-build \
                            --binary=true  \
                            --name="ext-registry-${TAGGED_APP_NAME}" \
                            --to-docker=true \
                            --to="${EXTERNAL_DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG}" \
                            --push-secret="${JENKINS_CRED_EXTERNAL_DOCKER_REGISTRY_PUSH_SECRET}" \
                            --source-secret="${JENKINS_CRED_GITHUB_ELUCIDATA_LOGIN}" \
                            --strategy="docker"
                    '''

                    sh '''
                    oc start-build ext-registry-${TAGGED_APP_NAME} \
                        --from-dir=${SOURCES_ROOT} \
                        --follow=true \
                        --wait=true
                    '''
            }

            post {
                always {
                    echo "Cleanup"
                    sh "rm -f ${SOURCES_ROOT}/id_rsa || true"
                }
            }
        }

        stage('deploy docker image to openshift') {
            when {
                expression { BRANCH_NAME == 'master' }
            }
            steps {
                 sh 'oc import-image ${TAGGED_APP_NAME} --from=${EXTERNAL_DOCKER_REGISTRY}/${APP_NAME}:latest --confirm'
                 sh '''
                    oc get dc/${TAGGED_APP_NAME} || oc new-app \
                        "${EXTERNAL_DOCKER_REGISTRY}/${APP_NAME}:latest" \
                        --name=${TAGGED_APP_NAME} \
                        -e DEBUG="${DEBUG}" \
                        -e SECRET_KEY="${SECRET_KEY}" \
                        -e ALLOWED_HOSTS="${ALLOWED_HOSTS}" \
                        -e DATABASE_HOST="${DATABASE_HOST}" \
                        -e DATABASE_USER="${DATABASE_USER}" \
                        -e DATABASE_PASSWORD="${DATABASE_PASSWORD}" \
                        -e DATABASE_NAME="${DATABASE_NAME}" \
                        -e DATABASE_PORT="${DATABASE_PORT}" \
                        -e DATABASE_MIN_POOL_SIZE="${DATABASE_MIN_POOL_SIZE}" \
                        -e DATABASE_MAX_POOL_SIZE="${DATABASE_MAX_POOL_SIZE}" \
                        -e DEPLOYMENT_ENVIRONMENT="${IMAGE_TAG}"
                    '''

            }
        }

        stage('wait for app to be healthy') {
            when {
                expression { BRANCH_NAME == 'master' }
            }
            steps {
                echo "wait for the new deployment to finish"
                retry(18) {
                    sh '''
                        sleep 10
                        oc rollout status dc/${TAGGED_APP_NAME} | grep 'successfully rolled out'
                        if [ $? -ne 0 ]; then exit 1; fi
                    '''
                }
            }
        }

        stage('update data') {
            when {
                expression { BRANCH_NAME == 'master' }
            }
            steps {
                echo "Get running OpenShift pod identifier"
                sh '''
                    a=0
                    while [ $a -lt 5 ]
                    do
                        if [ oc get pods --field-selector=status.phase=Running | grep "${TAGGED_APP_NAME}" == "" ]; then
                            sleep 2
                            i=$((i + 1))
                         else
                            oc get pods --field-selector=status.phase=Running \
                                | grep "${TAGGED_APP_NAME}" \
                                | cut -d ' ' -f 1 \
                                | awk -F- '{ print $(NF-1), $0 }' \
                                | sort -k1 -n -u \
                                | tail -n1 \
                                | cut -d ' ' -f 2 >${POD_NAME_FILE}
                            break
                        fi
                    done
                '''

                sh '''
                    oc exec $(cat ${POD_NAME_FILE}) python manage.py migrate

                '''
            }

            post {
                always {
                    echo "Clean up"
                    sh "rm -rf ${POD_NAME_FILE}"
                }
            }
        }
    }
    post {
        // Deletes all Openshift objects related to this CI build
        always {
            script {
                if ( ! ( BRANCH_NAME.startsWith('support/') || BRANCH_NAME == 'master' )) {
                    echo "cleanup..."
                    sh '''
                        (oc get all | grep -v ext-registry | grep "${TAGGED_APP_NAME}" | awk '{ print $1 }' | xargs -i oc delete {} ) || true
                    '''
                }
            }

            // TODO(Radek): Enable when TIG available in the Build cluster.
            // echo "Reporting test results to Influx"
            // step([
            //     $class: 'InfluxDbPublisher',
            //     customData: null,
            //     customDataMap: null,
            //     customPrefix: null,
            //     target: 'influxDB'
            // ])
        }
    }
}