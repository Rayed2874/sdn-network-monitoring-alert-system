from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template

from monitoring.ryu_adapter import RyuAdapter


BASE_DIR = Path(
    os.environ.get(
        "RYU_PROJECT_DIR",
        Path(__file__).resolve().parent.parent
    )
)

CONTROL_SERVER = "http://127.0.0.1:8765"

adapter = RyuAdapter(BASE_DIR)

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)


def telemetry_rows() -> list[dict]:

    path = BASE_DIR / "data" / "udp_telemetry.jsonl"

    if not path.exists():
        return []

    rows = []

    for line in path.read_text(encoding="utf-8").splitlines()[-100:]:

        try:
            item = json.loads(line)

            if isinstance(item, dict):
                rows.append(item)

        except json.JSONDecodeError:
            pass

    return rows


def control_request(endpoint: str):

    try:

        response = requests.post(
            f"{CONTROL_SERVER}{endpoint}",
            timeout=10
        )

        try:
            data = response.json()
        except ValueError:
            data = {
                "message": response.text
            }

        return jsonify(data), response.status_code

    except requests.RequestException as exc:

        return jsonify({
            "error": f"Mininet control server unavailable: {exc}"
        }), 503


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/data")
def api_data():

    summary = adapter.summary()
    telemetry = telemetry_rows()

    return jsonify({
        "dashboard": summary["dashboard"],
        "alerts": summary["alerts"],
        "flows": summary["flows"],
        "telemetry": telemetry,
    })


@app.post("/api/control/ping-all")
def ping_all():
    return control_request("/ping-all")


@app.post("/api/control/traffic/start")
def start_traffic():
    return control_request("/traffic/start")


@app.post("/api/control/traffic/stop")
def stop_traffic():
    return control_request("/traffic/stop")


@app.post("/api/control/link/down")
def link_down():
    return control_request("/link/down")


@app.post("/api/control/link/up")
def link_up():
    return control_request("/link/up")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
