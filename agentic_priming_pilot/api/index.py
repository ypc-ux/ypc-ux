"""Small web API wrapper around pipeline.py for deployment.

Exposes the Phase 1 + Phase 2 scraping pipeline over HTTP so it can be
triggered remotely instead of only via the CLI. Runs synchronously and
returns the resulting CSV, so keep `limit` low for a request that must
finish within the platform's function timeout.
"""
import os
import sys
import tempfile
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request, send_file  # noqa: E402

import pipeline  # noqa: E402

app = Flask(__name__)


@app.route("/", methods=["GET"])
@app.route("/api", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "agentic-priming-pilot"})


@app.route("/api/run", methods=["POST"])
def run_pipeline():
    payload = request.get_json(silent=True) or {}
    zip_code = str(payload.get("zip", "30035"))
    try:
        radius_miles = float(payload.get("radius_miles", 5.0))
    except (TypeError, ValueError):
        return jsonify({"error": "radius_miles must be a number"}), 400

    limit = payload.get("limit")
    try:
        limit = int(limit) if limit is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400

    out_path = os.path.join(tempfile.gettempdir(), f"shops-{uuid.uuid4().hex}.csv")
    try:
        pipeline.run(zip_code, radius_miles, limit, out_path)
    except Exception as exc:  # pipeline raises plain Exception/SystemExit on failure
        return jsonify({"error": str(exc)}), 500

    return send_file(
        out_path,
        mimetype="text/csv",
        as_attachment=True,
        download_name="shops.csv",
    )


# Local dev only; Vercel's Python runtime imports `app` directly.
if __name__ == "__main__":
    app.run(debug=True)
