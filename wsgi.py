"""Run locally with: python -m flask --app wsgi run --port 10001."""
from app import app
from runtime import install_runtime

install_runtime(app)
