"""The self-host package in deploy/ and the Dockerfile."""

import re
from pathlib import Path

import yaml

from backend.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_the_env_example_lists_every_setting_the_app_reads():
    keys = {
        line.split("=", 1)[0]
        for line in (ROOT / "deploy" / ".env.example").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    }

    assert {name.upper() for name in Settings.model_fields} - keys == set()


def test_every_image_is_pinned_and_the_app_runs_as_a_non_root_user():
    compose = yaml.safe_load((ROOT / "deploy" / "docker-compose.yml").read_text())
    dockerfile = (ROOT / "Dockerfile").read_text()
    services = compose["services"].values()
    built = {s["image"] for s in services if "build" in s}
    pulled = [s["image"] for s in services if s["image"] not in built]
    based = re.findall(r"^FROM (\S+)", dockerfile, re.MULTILINE)
    copied = re.findall(r"COPY --from=(\S+:\S+)", dockerfile)

    assert all("@sha256:" in image for image in pulled + based + copied)
    assert re.search(r"^USER app$", dockerfile, re.MULTILINE)
    assert "ports" not in compose["services"]["app"]
