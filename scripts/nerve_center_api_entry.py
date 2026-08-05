"""PyInstaller entry point for the packaged local API service."""

if __name__ == "__main__":
    from nerve_center.api.app import run

    run()
