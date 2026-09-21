"""Test-only barriers around the real example provider's transaction."""

import os
import time
from pathlib import Path

from examples.artifact_publication.mcp_server import serve
from examples.artifact_publication.storage import ArtifactStore


class PausedArtifactStore(ArtifactStore):
    def publish_artifact(self, **arguments):
        before = float(os.environ.get("FAKE_SLOW_BEFORE", "0"))
        after = float(os.environ.get("FAKE_SLOW", "0"))
        if before:
            Path("before-commit").touch()
            time.sleep(before)
        result = super().publish_artifact(**arguments)
        if after:
            Path("after-commit").touch()
            time.sleep(after)
        return result


if __name__ == "__main__":
    serve(PausedArtifactStore(os.environ["FAKE_STATE"]))
