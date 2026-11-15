"""Rebuild the complete current House project from pinned, normalized inputs."""

import json

from . import (
    house_candidates,
    house_members,
    house_study,
    rebuild,
    rebuild_package,
    rebuild_publication,
)


def build():
    rebuild.replay()
    house_candidates.build()
    house_members.build()
    summary = house_study.build()
    rebuild_publication.build()
    downloads = rebuild_package.build()
    return {"study": summary, "downloads": downloads}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
