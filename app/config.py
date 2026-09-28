"""
App configuration.

!!! INTENTIONALLY INSECURE - DEMO BRANCH ONLY !!!
The credentials below are FAKE (they do not belong to any AWS account).
They exist so the pipeline's Secret Scan gate (Gitleaks) has something to catch.
Never hardcode real credentials - read them from environment variables instead.
"""

# Fake AWS-style credentials (hardcoded secret -> Gitleaks + Semgrep will flag this)
AWS_ACCESS_KEY_ID = "AKIAQ3FAKEDEMO7KEY2X"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYFAKEDEMOKEY"
AWS_REGION = "us-east-1"
