from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def data_path(*parts: str) -> Path:
    return BASE_DIR / "data" / Path(*parts)


def state_path(*parts: str) -> Path:
    return BASE_DIR / "state" / Path(*parts)


def assets_path(*parts: str) -> Path:
    return BASE_DIR / "assets" / Path(*parts)
