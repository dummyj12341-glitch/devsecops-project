# ---------------------------------------------------------------------------
# Custom Jenkins image for the DevSecOps pipeline.
#
# Every tool the pipeline needs is installed INSIDE this image, so the
# Jenkinsfile just calls `gitleaks`, `semgrep`, `trivy`, `docker` directly.
# (Running scanners as sibling containers via the Docker socket causes
#  volume-path problems, because the workspace path inside Jenkins does not
#  exist on the host.)
# ---------------------------------------------------------------------------
FROM jenkins/jenkins:lts-jdk17

# Tool versions - bump these to upgrade.
ARG GITLEAKS_VERSION=8.30.1
ARG TRIVY_VERSION=0.74.0
ARG SEMGREP_VERSION=1.178.0

USER root

# 1) Base packages: Python (for unit tests + semgrep), curl (health check)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg python3 python3-pip python3-venv \
 && rm -rf /var/lib/apt/lists/*

# 2) Docker CLI + compose plugin from Docker's official apt repository.
#    Only the CLI is installed; it talks to the HOST's Docker daemon through
#    the mounted /var/run/docker.sock.
RUN install -m 0755 -d /etc/apt/keyrings \
 && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
 && rm -rf /var/lib/apt/lists/*

# 3) Gitleaks (secret scanner) - single static binary from GitHub releases.
RUN ARCH=$(dpkg --print-architecture) \
 && case "$ARCH" in amd64) GL_ARCH=x64 ;; arm64) GL_ARCH=arm64 ;; *) echo "unsupported arch $ARCH" && exit 1 ;; esac \
 && curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${GL_ARCH}.tar.gz" \
      | tar -xz -C /usr/local/bin gitleaks \
 && gitleaks version

# 4) Trivy (dependency + image vulnerability scanner) - official .deb package.
RUN ARCH=$(dpkg --print-architecture) \
 && case "$ARCH" in amd64) TV_ARCH=64bit ;; arm64) TV_ARCH=ARM64 ;; *) echo "unsupported arch $ARCH" && exit 1 ;; esac \
 && curl -fsSL -o /tmp/trivy.deb "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-${TV_ARCH}.deb" \
 && dpkg -i /tmp/trivy.deb && rm /tmp/trivy.deb \
 && trivy --version

# 5) Semgrep (SAST). Debian blocks system-wide `pip install` (PEP 668), so
#    semgrep gets its own virtualenv and is symlinked onto the PATH.
RUN python3 -m venv /opt/semgrep \
 && /opt/semgrep/bin/pip install --no-cache-dir "semgrep==${SEMGREP_VERSION}" \
 && ln -s /opt/semgrep/bin/semgrep /usr/local/bin/semgrep \
 && semgrep --version

USER jenkins

# 6) Jenkins plugins - pre-installed so the setup wizard has nothing to download.
COPY --chown=jenkins:jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
