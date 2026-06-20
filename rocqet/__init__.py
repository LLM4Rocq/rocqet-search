"""Rocqet semantic search tooling."""

import os as _os

__all__ = ["__version__"]

__version__ = "0.1.0"

# Back-compat: the project was renamed roqet -> rocqet. Honor the legacy ROQET_*
# environment prefix by mapping any such var onto its ROCQET_* equivalent (unless
# the new name is already set). This keeps existing deployments / MCP client
# configs working without an env edit. Remove in a future major version.
for _key, _val in list(_os.environ.items()):
    if _key.startswith("ROQET_"):
        _os.environ.setdefault("ROCQET_" + _key[len("ROQET_"):], _val)
