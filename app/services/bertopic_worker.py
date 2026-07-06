from __future__ import annotations

import sys

from .bertopic_service import worker_main


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.services.bertopic_worker <payload_path>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(worker_main(sys.argv[1]))
