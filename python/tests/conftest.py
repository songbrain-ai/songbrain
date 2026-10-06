import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SONGBRAIN_OFFLINE") not in (None, "", "0"):
        skip = pytest.mark.skip(reason="SONGBRAIN_OFFLINE is set")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip)
