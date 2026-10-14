"""Shared result line for the eager and lazy entry points."""

import json
import resource
import sys
import time


def finish(t0: float, t_import: float, answer, style: str, target: str) -> None:
    t_end = time.perf_counter()
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes. Linux reports kilobytes.
    if sys.platform != "darwin":
        rss *= 1024
    json.dump(
        {
            "style": style,
            "target": target,
            "import_ms": (t_import - t0) * 1000,
            "total_ms": (t_end - t0) * 1000,
            "rss_bytes": rss,
            "answer": answer,
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
