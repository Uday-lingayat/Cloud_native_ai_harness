from pathlib import Path

import app


def test_backend_package_imports() -> None:
    backend = Path(__file__).resolve().parents[1]
    assert Path(app.__file__).resolve() == backend / "app" / "__init__.py"
