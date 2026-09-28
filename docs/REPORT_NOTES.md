# Report Notes: DevSecOps Pipeline with Automated Security Gates for Container Deployment

> Draft sections for the college project report. Expand them in your own words and add screenshots from the Jenkins runs where marked 📸.

---

## 1. Problem Statement

Modern teams ship software many times a day with CI/CD pipelines. Security checks are often done by hand, late in the release cycle, or not at all. Vulnerabilities then reach production:

- **Leaked secrets.** API keys and passwords committed to git are a leading cause of cloud breaches. Deleting the file afterwards does not help, because the secret stays in git history.
- **Insecure code.** Patterns such as running Flask in debug mode or building shell commands from user input give attackers remote code execution.
- **Vulnerable dependencies.** Most application code is third-party. One outdated library (for example PyYAML < 5.4, CVE-2020-14343) can compromise the whole service.
- **Vulnerable container images.** Base images contain OS packages with their own CVEs.

The problem is to **shift security left**: detect these issues automatically on every commit, and **block** the deployment of insecure builds, without slowing developers down.

## 2. Objectives

1. Build a CI/CD pipeline in Jenkins that automatically tests, builds and deploys a containerised Python application.
2. Add four automated **security gates**: secret scanning, static application security testing (SAST), software composition analysis (dependency scanning) and container image scanning.
3. **Fail the build** automatically on any detected secret or HIGH/CRITICAL finding, so vulnerable code can never be deployed.
4. Produce a machine-readable **report** for every scan and archive it with each build, for auditing.
5. Harden the deployed container: slim base image, non-root user, read-only filesystem, health check.
6. Demonstrate the pipeline with a *vulnerable* branch, which must be blocked, and a *fixed* branch, which must be deployed.

## 3. Tools Used and Why

| Tool | Category | Why it was chosen |
|---|---|---|
| **Git + GitHub** | Version control | Source of truth. Branches let us compare vulnerable and fixed versions. |
| **Jenkins** (declarative pipeline) | CI/CD orchestration | Open source and widely used in industry. The pipeline is stored as code (`Jenkinsfile`) and versioned with the app. Multibranch jobs build every branch automatically. |
| **Docker / Docker Compose** | Containerisation & deployment | Reproducible builds and the same environment everywhere. Compose gives a one-command deployment with health checks. |
| **Python Flask + pytest** | Sample app & testing | Small and easy to understand. pytest writes JUnit XML, which Jenkins displays. |
| **Gitleaks** | Secret scanning | Fast single binary with 150+ built-in rules (AWS, GitHub, Slack, private keys…). Scans the **entire git history**, not only the current files. |
| **Semgrep** | SAST | Rules look like the code they match, so they are easy to read and write. Rules map to CWE/OWASP categories. Runs offline with local rules. |
| **Trivy** | SCA + image scanning | One tool for both dependency (`trivy fs`) and container image (`trivy image`) scanning. Free, uses several vulnerability databases (NVD, GitHub Advisories, distro trackers), and supports JSON output and severity filtering. |

## 4. Methodology

### 4.1 System architecture
Jenkins runs in a Docker container built from a custom image with all tools pre-installed. It controls the host's Docker engine through the mounted Docker socket. The socket's group ID is added to the `jenkins` user, so Jenkins does not have to run as root. *(Insert the Mermaid architecture diagram from the README.)*

### 4.2 Pipeline design
The pipeline is ordered **cheap and fast checks first, expensive checks later** (fail fast):

1. **Checkout**: the Multibranch job clones the branch that changed.
2. **Unit Tests**: pytest inside a Python virtual environment. The results are published as JUnit.
3. **Secret Scan**: `gitleaks git` over the whole commit history.
4. **SAST**: `semgrep --error` with 5 custom rules (CWE-489, CWE-78, CWE-95, CWE-502, CWE-798).
5. **Dependency Scan**: `trivy fs --severity HIGH,CRITICAL --exit-code 1` over the pinned requirements.
6. **Docker Build**: the image is tagged `<branch>-<build number>` for traceability.
7. **Image Scan**: `trivy image --ignore-unfixed` on the exact image that will be deployed.
8. **Deploy**: `docker compose up -d --no-build` (so the scanned image is the one deployed), then a `curl /health` smoke test with retries.

Gate mechanism: each scanner returns exit code 1 on a finding. Jenkins then marks the stage failed and skips all later stages. The `post` block archives the reports, deletes the rejected image and optionally sends a Telegram or email alert.

### 4.3 Container hardening
- `python:3.12-slim` base image, which has fewer packages and so a smaller attack surface
- the app runs as the unprivileged `appuser` (UID 10001)
- read-only root filesystem, with `tmpfs` for `/tmp`
- production WSGI server (gunicorn) instead of the Flask development server
- a `HEALTHCHECK` that lets Docker and the pipeline confirm the app is really up
- `.dockerignore` keeps `.git`, tests and reports out of the image

### 4.4 Test scenario
Two branches share the same pipeline:
- `vulnerable`: a fake AWS access key, `PyYAML==5.3.1` (CRITICAL CVE-2020-14343), `app.run(debug=True)` and `subprocess.run(..., shell=True)`.
- `main`: the same app with all four issues fixed.

## 5. Expected Results

| Branch | Unit Tests | Gitleaks | Semgrep | Trivy fs | Trivy image | Deploy | Overall |
|---|---|---|---|---|---|---|---|
| `vulnerable` | ✅ pass | ❌ **fail** (AWS key) | ⏭ skipped | ⏭ skipped | ⏭ skipped | ⏭ skipped | 🔴 FAILURE |
| `main` | ✅ 7/7 pass | ✅ no leaks | ✅ 0 findings | ✅ 0 HIGH/CRIT | ✅ 0 HIGH/CRIT | ✅ healthy | 🟢 SUCCESS |

When the same scanners are run with `scripts/run-scans-locally.sh` (which does not stop at the first failure), the `vulnerable` branch fails **all four** gates:
- Gitleaks: `aws-access-token` rule
- Semgrep: `flask-debug-enabled`, `subprocess-shell-true`, `hardcoded-aws-access-key`
- Trivy fs: PyYAML 5.3.1, CVE-2020-14343 (CRITICAL, fixed in 5.4)
- Trivy image: the same PyYAML CVE inside the image, plus Trivy's built-in secret scanner finds the AWS key in `/app/config.py` (defence in depth)

📸 Screenshots to include:
- Stage View of the red `vulnerable` build
- Console output with the Gitleaks finding
- Stage View of the green `main` build
- the Test Result page
- the build artifacts list
- `curl /health` output and `docker ps` showing `(healthy)`

## 6. Conclusion

The project shows that security can be **automated and enforced** inside a CI/CD pipeline instead of being a manual step at the end. With free, open-source tools (Gitleaks, Semgrep and Trivy), every commit is checked for leaked secrets, insecure code, vulnerable libraries and vulnerable container packages within minutes. A build with any serious finding is blocked before deployment. The vulnerable branch was stopped automatically, and the fixed branch was built, scanned and deployed without manual intervention.

**Limitations and future work**
- Add **DAST**, for example OWASP ZAP against the deployed app.
- Sign images and generate an SBOM (Cosign, `trivy sbom`).
- Use a secrets manager (Vault, AWS Secrets Manager) and rotate keys automatically.
- Deploy to Kubernetes with policy enforcement (OPA Gatekeeper or Kyverno).
- Run builds on dedicated Jenkins agents instead of sharing the host's Docker socket.
- Add a quality dashboard such as SonarQube or DefectDojo to track findings over time.
