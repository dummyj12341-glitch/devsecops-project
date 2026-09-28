# ---------------------------------------------------------------------------
# Notes API container image
#  - slim base image  -> fewer OS packages = smaller attack surface
#  - non-root user    -> a compromised app cannot act as root in the container
#  - gunicorn         -> production WSGI server (Flask's dev server is not for prod)
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Don't write .pyc files, and flush logs straight to `docker logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so this layer is cached when only code changes.
COPY app/requirements.txt .
RUN pip install -r requirements.txt

# Copy only the application code (tests are not shipped to production).
COPY app/*.py ./

# Create an unprivileged user and switch to it.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 5000

# Docker marks the container "healthy" once /health answers.
# (python is used instead of curl because curl is not in the slim image)
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
