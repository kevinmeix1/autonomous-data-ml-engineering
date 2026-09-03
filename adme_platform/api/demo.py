from __future__ import annotations

from adme_platform.api.cli import seed


def seed_demo() -> None:
    seed(42)


if __name__ == "__main__":
    seed_demo()
