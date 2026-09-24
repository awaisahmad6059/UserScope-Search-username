"""UserScope Engine Package.

This package contains the core search engine used by the UserScope
username intelligence dashboard.

"""

import pathlib

try:
    import tomllib as tomli
except ImportError:  # Python 3.10 and earlier
    import tomli


def get_version() -> str:
    """Fetch the version number of the installed package."""
    try:
        pyproject_path: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            pyproject_data = tomli.load(f)
        return pyproject_data["project"]["version"]
    except Exception:
        return "0.1.0"

# This variable is only used to check for ImportErrors induced by users running as script rather than as module or package
import_error_test_var = None

__shortname__   = "UserScope"
__longname__    = "UserScope: Username Intelligence"
__version__     = get_version()

forge_api_latest_release = "https://api.github.com/repos/sherlock-project/sherlock/releases/latest"
