"""``python -m factory.openarcade`` — launch the wall with default env."""

from __future__ import annotations

from .app import run_wall


def main() -> None:
    run_wall()


if __name__ == "__main__":
    main()
