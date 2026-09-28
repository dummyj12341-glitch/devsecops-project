"""
Notes API - a tiny Flask REST service used as the sample application
for the DevSecOps pipeline.

Endpoints
---------
GET  /health  -> {"status": "ok"}           (used by Docker healthcheck + Deploy stage)
GET  /notes   -> list of all notes
POST /notes   -> create a note, body: {"text": "..."}

Notes are kept in memory, so they disappear when the container restarts.
That keeps the project simple: no database to set up for the demo.
"""
import subprocess

from flask import Flask, jsonify, request

import config  # noqa: F401  (INSECURE demo: hardcoded fake AWS credentials live here)

app = Flask(__name__)

# In-memory "database": a list of {"id": int, "text": str}
NOTES = []


@app.get("/health")
def health():
    """Liveness check. Returns 200 when the app is running."""
    return jsonify(status="ok"), 200


@app.get("/notes")
def list_notes():
    """Return every stored note."""
    return jsonify(NOTES), 200


@app.post("/notes")
def create_note():
    """Create a note from JSON like {"text": "buy milk"}."""
    data = request.get_json(silent=True) or {}
    text = data.get("text")

    # Basic input validation: text must be a non-empty string.
    if not isinstance(text, str) or not text.strip():
        return jsonify(error="'text' is required and must be a non-empty string"), 400

    note = {"id": len(NOTES) + 1, "text": text.strip()}
    NOTES.append(note)
    return jsonify(note), 201


@app.get("/ping")
def ping():
    """INSECURE demo endpoint: pings a host given in the query string.

    shell=True + user input = OS command injection
    (e.g. /ping?host=127.0.0.1;cat /etc/passwd). Semgrep flags this.
    """
    host = request.args.get("host", "127.0.0.1")
    result = subprocess.run(f"ping -c 1 {host}", shell=True, capture_output=True, text=True)
    return jsonify(output=result.stdout), 200


if __name__ == "__main__":
    # INSECURE demo: debug=True enables the Werkzeug debugger (remote code execution
    # if exposed) and binds to all interfaces. Semgrep flags this.
    app.run(host="0.0.0.0", port=5000, debug=True)
