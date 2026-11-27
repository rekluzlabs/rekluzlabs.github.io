"""Refuse a publication commit when any unrelated tracked path changed."""
import subprocess

ALLOWED = {f"VaultCuisine-Advisories/gemini-{kind}.json" for kind in ("lifecycle", "compatibility", "pricing")}


def check(paths):
    unexpected = set(paths) - ALLOWED
    if unexpected:
        raise ValueError(f"unexpected modified paths: {sorted(unexpected)}")
    return True


if __name__ == "__main__":
    changed = subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines()
    check(changed)
