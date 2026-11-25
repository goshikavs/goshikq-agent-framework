"""The Windows installer rejects a SHA256 that does not match the file."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(os.name != "nt", reason="install.ps1 is the Windows installer")
def test_install_ps1_rejects_checksum_mismatch(tmp_path: Path) -> None:
    sample = tmp_path / "archive.bin"
    sample.write_bytes(b"not-a-release")
    script = ROOT / "scripts" / "install.ps1"
    command = (
        f". '{script}'; "
        f"try {{ Test-GoshikqSha256 -Path '{sample}' -Expected 'deadbeef' ; exit 0 }} "
        "catch { Write-Output $_.Exception.Message; exit 2 }"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "SHA256 mismatch" in (proc.stdout + proc.stderr)


@pytest.mark.skipif(os.name != "nt", reason="install.ps1 is the Windows installer")
def test_install_ps1_accepts_matching_checksum(tmp_path: Path) -> None:
    sample = tmp_path / "archive.bin"
    sample.write_bytes(b"not-a-release")
    import hashlib

    digest = hashlib.sha256(sample.read_bytes()).hexdigest()
    script = ROOT / "scripts" / "install.ps1"
    command = (
        f". '{script}'; "
        f"try {{ Test-GoshikqSha256 -Path '{sample}' -Expected '{digest}' ; exit 0 }} "
        "catch { Write-Output $_.Exception.Message; exit 2 }"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(os.name != "nt", reason="install.ps1 is the Windows installer")
def test_install_ps1_rejects_unsupported_architecture() -> None:
    script = ROOT / "scripts" / "install.ps1"
    command = (
        f". '{script}'; "
        "try { Resolve-GoshikqPlatform 'IA64'; exit 0 } "
        "catch { Write-Output $_.Exception.Message; exit 3 }"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "Unsupported Windows architecture" in (proc.stdout + proc.stderr)
