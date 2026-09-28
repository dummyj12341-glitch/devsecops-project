// ===========================================================================
// DevSecOps Pipeline with Automated Security Gates for Container Deployment
//
// Checkout -> Unit Tests -> Secret Scan -> SAST -> Dependency Scan
//          -> Docker Build -> Image Scan -> Deploy
//
// Every security stage is a GATE: the tool exits non-zero when it finds a
// secret or a HIGH/CRITICAL issue, `sh` then fails the stage, and Jenkins
// skips all later stages. So Deploy can only run when every gate passed.
// All tools (gitleaks, semgrep, trivy, docker) are installed in the Jenkins
// image - see jenkins/Dockerfile.
// ===========================================================================

// Set to true in the Deploy stage; lets the post block know whether a
// half-finished deployment needs to be torn down.
def deployStarted = false

pipeline {
    agent any

    options {
        skipDefaultCheckout(true)          // we check out explicitly in the Checkout stage
        disableConcurrentBuilds()          // one build per branch at a time (shared port 5000)
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
    }

    environment {
        IMAGE_NAME = 'notes-api'
        // Unique per branch + build, e.g. "main-7". Also used by docker-compose.yml.
        IMAGE_TAG  = "${env.BRANCH_NAME.replaceAll('[^A-Za-z0-9_.-]', '-')}-${env.BUILD_NUMBER}"
        REPORTS    = 'reports'
        // Trivy's ~100 MB vulnerability DB is cached here between builds.
        TRIVY_CACHE_DIR = '/var/jenkins_home/.cache/trivy'
        SEMGREP_ENABLE_VERSION_CHECK = '0'
        // App URL as seen from inside the Jenkins container (see jenkins/docker-compose.yml).
        HEALTH_URL = 'http://host.docker.internal:5000/health'

        // ---- Optional failure notification (disabled by default) ----------
        // Set NOTIFY_ENABLED to 'true' and NOTIFY_CHANNEL to 'telegram' or 'email'.
        // See README section "Failure notifications" for the credentials needed.
        NOTIFY_ENABLED = 'false'
        NOTIFY_CHANNEL = 'telegram'
        NOTIFY_EMAIL   = 'you@example.com'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                // Fresh reports folder for this build.
                sh 'rm -rf "$REPORTS" && mkdir -p "$REPORTS"'
                sh 'git log -1 --oneline'
            }
        }

        stage('Unit Tests') {
            steps {
                // Isolated virtualenv so builds never pollute the Jenkins image.
                sh '''
                    python3 -m venv .venv
                    .venv/bin/pip install --quiet --disable-pip-version-check -r app/requirements-dev.txt
                    .venv/bin/pytest app/tests -v --junitxml="$REPORTS/junit.xml"
                '''
            }
        }

        stage('Secret Scan (Gitleaks)') {
            steps {
                // Scans the whole git history of the branch, not just the latest files:
                // a secret that was committed and later deleted is still leaked.
                // --log-opts=HEAD limits the scan to commits reachable from THIS branch
                // (by default gitleaks runs `git log --all`, which would also pick up
                //  other branches that Jenkins fetched, e.g. `vulnerable` while building `main`).
                sh '''
                    gitleaks git . \
                      --log-opts=HEAD \
                      --config .gitleaks.toml \
                      --redact --no-banner \
                      --report-format json --report-path "$REPORTS/gitleaks.json" \
                      --exit-code 1
                '''
            }
        }

        stage('SAST (Semgrep)') {
            steps {
                // --error => exit code 1 if any rule matches (all rules are severity ERROR).
                // The first run writes the JSON report and decides pass/fail;
                // the second prints a readable summary to the console.
                sh '''
                    rc=0
                    semgrep scan --config .semgrep.yml --metrics=off --error --quiet \
                      --json --output "$REPORTS/semgrep.json" app/ || rc=$?
                    semgrep scan --config .semgrep.yml --metrics=off --quiet app/ | tee "$REPORTS/semgrep.txt"
                    exit $rc
                '''
            }
        }

        stage('Dependency Scan (Trivy fs)') {
            steps {
                // Checks the pinned versions in app/requirements*.txt against known CVEs.
                sh '''
                    trivy fs --no-progress --scanners vuln \
                      --severity HIGH,CRITICAL --ignorefile .trivyignore \
                      --format table --output "$REPORTS/trivy-fs.txt" app/
                    cat "$REPORTS/trivy-fs.txt"
                    trivy fs --no-progress --scanners vuln \
                      --severity HIGH,CRITICAL --ignorefile .trivyignore \
                      --format json --output "$REPORTS/trivy-fs.json" \
                      --exit-code 1 app/
                '''
            }
        }

        stage('Docker Build') {
            steps {
                sh 'docker build -t "$IMAGE_NAME:$IMAGE_TAG" .'
            }
        }

        stage('Image Scan (Trivy)') {
            steps {
                // Scans OS packages + Python packages inside the built image.
                // --ignore-unfixed: skip CVEs that have no patched version yet
                // (nothing we could upgrade to, so they should not block a release).
                sh '''
                    trivy image --no-progress \
                      --severity HIGH,CRITICAL --ignore-unfixed --ignorefile .trivyignore \
                      --format table --output "$REPORTS/trivy-image.txt" "$IMAGE_NAME:$IMAGE_TAG"
                    cat "$REPORTS/trivy-image.txt"
                    trivy image --no-progress \
                      --severity HIGH,CRITICAL --ignore-unfixed --ignorefile .trivyignore \
                      --format json --output "$REPORTS/trivy-image.json" \
                      --exit-code 1 "$IMAGE_NAME:$IMAGE_TAG"
                '''
            }
        }

        stage('Deploy') {
            // Only the main branch is deployed; other branches stop after the gates.
            when { branch 'main' }
            steps {
                script { deployStarted = true }
                // --no-build: deploy exactly the image that Trivy just scanned.
                // IMAGE_TAG is read by docker-compose.yml.
                sh '''
                    docker compose up -d --no-build --force-recreate
                    echo "Waiting for $HEALTH_URL ..."
                    for i in $(seq 1 15); do
                      if curl -fsS "$HEALTH_URL"; then
                        echo; echo "App is healthy."
                        exit 0
                      fi
                      sleep 2
                    done
                    echo "Health check failed"
                    docker compose logs --tail 50
                    exit 1
                '''
            }
        }
    }

    post {
        always {
            // Test results appear in the job's "Test Result" page.
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
            // Every scan report is downloadable from the build page.
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true, fingerprint: true
            // Remove dangling image layers left over from builds.
            sh 'docker image prune -f || true'
        }
        success {
            echo "PASSED: all security gates green. Deployed ${IMAGE_NAME}:${IMAGE_TAG} (main branch only) -> http://localhost:5000/health"
        }
        failure {
            echo 'FAILED: a quality/security gate blocked this build. See the stage log and the archived reports.'
            script {
                // Tear down a deployment that started but failed its health check.
                if (deployStarted) {
                    sh 'docker compose down || true'
                }
                // An image that failed its gates must never be deployed - delete it.
                sh 'docker rmi "$IMAGE_NAME:$IMAGE_TAG" 2>/dev/null || true'

                if (env.NOTIFY_ENABLED == 'true') {
                    def msg = "Jenkins build FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER} - ${env.BUILD_URL}"
                    if (env.NOTIFY_CHANNEL == 'telegram') {
                        // Credentials of type "Secret text" with these IDs must exist in Jenkins.
                        withCredentials([string(credentialsId: 'telegram-bot-token', variable: 'TG_TOKEN'),
                                         string(credentialsId: 'telegram-chat-id', variable: 'TG_CHAT')]) {
                            withEnv(["TG_MSG=${msg}"]) {
                                // Single quotes: the shell (not Groovy) expands the secrets,
                                // so they are never written into the build log.
                                sh 'curl -fsS -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" --data-urlencode "chat_id=${TG_CHAT}" --data-urlencode "text=${TG_MSG}" >/dev/null || true'
                            }
                        }
                    } else if (env.NOTIFY_CHANNEL == 'email') {
                        // Needs SMTP configured in Manage Jenkins -> System -> Extended E-mail Notification.
                        emailext to: env.NOTIFY_EMAIL,
                                 subject: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                                 body: "${msg}\n\nReports are attached to the build as artifacts."
                    }
                }
            }
        }
    }
}
