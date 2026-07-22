#!/usr/bin/env python3
"""Install dependencies for history-search skill."""
import subprocess, sys

deps = ["prompt_toolkit", "wcwidth"]
for dep in deps:
    print(f"Installing {dep}...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", dep],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  OK: {dep}")
    else:
        print(f"  ERROR: {result.stderr.strip()}")

print("\nAll dependencies installed!")
