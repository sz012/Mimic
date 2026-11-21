from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.features import faces


def main() -> int:
    if not faces.installed():
        print("insightface nie jest zainstalowane, pomijam pobieranie modelu twarzy")
        return 0
    embedder, reason = faces.get_embedder()
    print("model twarzy gotowy" if embedder else reason)
    return 0 if embedder else 1


if __name__ == "__main__":
    raise SystemExit(main())
