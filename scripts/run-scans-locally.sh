#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Runs the pipeline's security gates on your machine WITHOUT Jenkins, using the
# same Jenkins image (so the tool versions match the pipeline exactly).
#
# Unlike Jenkins (which stops at the first failing gate), this script runs
# EVERY gate and prints a summary - handy to show in a demo that the
# `vulnerable` branch trips all four gates.
#
# Usage (from the repo root, after building the Jenkins image):
#   ./scripts/run-scans-locally.sh
# Reports are written to ./reports/
# ---------------------------------------------------------------------------
set -u
cd "$(dirname "$0")/.."

JENKINS_IMAGE=devsecops-jenkins:latest
APP_IMAGE=notes-api:local-scan
DOCKER_GID=$(stat -c %g /var/run/docker.sock)

mkdir -p reports
# Trivy DB cache on the host so the ~100 MB database is downloaded only once.
TRIVY_CACHE="${HOME}/.cache/trivy"
mkdir -p "${TRIVY_CACHE}"

# Build the app image on the host so the image scan has something to scan.
echo "==> Building ${APP_IMAGE}"
docker build -q -t "${APP_IMAGE}" . >/dev/null || { echo "docker build failed"; exit 1; }

# Run the scanner commands inside the Jenkins image with the repo mounted.
docker run --rm \
  --user "$(id -u)" --group-add "${DOCKER_GID}" \
  -e HOME=/tmp -e TRIVY_CACHE_DIR=/tmp/.trivy-cache \
  -v "${TRIVY_CACHE}":/tmp/.trivy-cache \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD":/src -w /src \
  --entrypoint bash "${JENKINS_IMAGE}" -c '
    git config --global --add safe.directory /src
    declare -A RESULT

    echo; echo "==> [1/4] Secret Scan (Gitleaks)"
    gitleaks git . --log-opts=HEAD --config .gitleaks.toml --redact --no-banner \
      --report-format json --report-path reports/gitleaks.json --exit-code 1
    RESULT[gitleaks]=$?

    echo; echo "==> [2/4] SAST (Semgrep)"
    semgrep scan --config .semgrep.yml --error --metrics=off --quiet \
      --json --output reports/semgrep.json app/
    rc=$?
    semgrep scan --config .semgrep.yml --metrics=off --quiet app/ || true
    RESULT[semgrep]=$rc

    echo; echo "==> [3/4] Dependency Scan (Trivy fs)"
    trivy fs --no-progress --scanners vuln --severity HIGH,CRITICAL --ignorefile .trivyignore \
      --exit-code 1 --format json --output reports/trivy-fs.json app/
    rc=$?
    trivy fs --no-progress --scanners vuln --severity HIGH,CRITICAL --ignorefile .trivyignore \
      --format table --quiet app/
    RESULT[trivy-fs]=$rc

    echo; echo "==> [4/4] Image Scan (Trivy image)"
    trivy image --no-progress --severity HIGH,CRITICAL --ignore-unfixed --ignorefile .trivyignore \
      --exit-code 1 --format json --output reports/trivy-image.json '"${APP_IMAGE}"'
    rc=$?
    trivy image --no-progress --severity HIGH,CRITICAL --ignore-unfixed --ignorefile .trivyignore \
      --format table --quiet '"${APP_IMAGE}"'
    RESULT[trivy-image]=$rc

    echo; echo "================ SUMMARY ================"
    fail=0
    for gate in gitleaks semgrep trivy-fs trivy-image; do
      if [ "${RESULT[$gate]}" -eq 0 ]; then echo "PASS  $gate"; else echo "FAIL  $gate"; fail=1; fi
    done
    exit $fail
  '
