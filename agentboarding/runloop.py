"""Re-run-to-prove-delta loop. The proof the gap closed: a fresh agent against
the patched surface scores higher than the baseline.

    prove_fix: (1) baseline AX on the original surface; (2) apply the Fix to a
    fresh copy; (3) spawn a brand-new sandboxed agent against the patched surface
    (served over HTTP) -> its trajectory; (4) compute new AX; (5) Delta.

For deterministic offline CI the loop uses committed pre-recorded post-fix
goldens instead of a live re-run (clearly the offline path).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional, Union

from .axscore import compute_ax
from .models import Delta, Trajectory

TrajLike = Union[Trajectory, str, Path]


def _as_traj(x: TrajLike) -> Trajectory:
    if isinstance(x, Trajectory):
        return x
    return Trajectory.load(x)


def compute_delta(baseline: TrajLike, postfix: TrajLike) -> Delta:
    before = compute_ax(_as_traj(baseline)).score
    after = compute_ax(_as_traj(postfix)).score
    return Delta(before=before, after=after, improved=after > before)


def prove_fix(
    goal=None,
    fixture=None,
    fix=None,
    *,
    baseline: TrajLike,
    postfix: Optional[TrajLike] = None,
    rerun: Optional[Callable[[], Trajectory]] = None,
) -> Delta:
    """Offline: pass a committed `postfix` golden. Live: pass a `rerun` callable
    that applies `fix`, spawns a fresh agent, and returns its Trajectory."""
    if postfix is None and rerun is None:
        raise ValueError("prove_fix needs a committed `postfix` golden or a live `rerun` callable")
    post = _as_traj(postfix) if postfix is not None else rerun()
    return compute_delta(baseline, post)


def _main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Re-run-to-prove-delta")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--postfix", required=True)
    args = ap.parse_args(argv)
    delta = compute_delta(args.baseline, args.postfix)
    print(json.dumps(delta.to_dict()))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
