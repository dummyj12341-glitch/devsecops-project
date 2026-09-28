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
from flask import Flask, jsonify, request

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


if __name__ == "__main__":
    # Local development only. In the container the app is served by gunicorn.
    # debug is intentionally OFF (debug=True would expose the Werkzeug debugger).
    app.run(host="127.0.0.1", port=5000, debug=False)
