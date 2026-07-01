"""Vertex AI smoke test — confirms ADC auth routes requests to Synergy's trial credits.

Run AFTER:  gcloud auth application-default login
Override project/location/model via env if needed (defaults match the console).
"""

import os

from google import genai

PROJECT = os.environ.get("VERTEX_PROJECT", "synergy-498606")
LOCATION = os.environ.get("VERTEX_LOCATION", "us-central1")
MODEL = os.environ.get("VERTEX_MODEL", "gemini-2.5-flash-lite")  # repo judge model

client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)

resp = client.models.generate_content(
    model=MODEL,
    contents="Reply with exactly: Vertex credits OK",
)
print(f"[{PROJECT}/{LOCATION} {MODEL}] {resp.text}")
