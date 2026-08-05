"""PyInstaller entry point for the packaged local API service."""

from nerve_center.api.app import run


if __name__ == "__main__":
    run()
