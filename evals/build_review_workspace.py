#!/usr/bin/env python
"""Build Skill Creator metadata, grading, and benchmark files from saved eval outputs."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from grade_outputs import grade


def stats(values: list[float]) -> dict:
    return {
        "mean": statistics.mean(values) if values else 0,
        "stddev": statistics.pstdev(values) if len(values) > 1 else 0,
        "min": min(values) if values else 0,
        "max": max(values) if values else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    evals = json.loads((args.skill_root / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]
    runs = []
    rates = {"with_skill": [], "old_skill": []}
    for item in evals:
        eval_dir = args.workspace / f"eval-{item['id']}-{item['name']}"
        metadata = {
            "eval_id": item["id"], "eval_name": item["name"],
            "prompt": item["prompt"], "assertions": item["expectations"],
        }
        (eval_dir / "eval_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for configuration in ("with_skill", "old_skill"):
            run_dir = eval_dir / configuration
            response = run_dir / "outputs" / "response.md"
            result = grade(item["id"], response.read_text(encoding="utf-8"))
            (run_dir / "grading.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            rate = result["summary"]["pass_rate"]
            rates[configuration].append(rate)
            runs.append({
                "eval_id": item["id"], "eval_name": item["name"],
                "configuration": configuration, "run_number": 1,
                "result": {
                    "pass_rate": rate, "passed": result["summary"]["passed"],
                    "failed": result["summary"]["failed"], "total": result["summary"]["total"],
                    "time_seconds": 0, "tokens": 0, "tool_calls": 0, "errors": 0,
                },
                "expectations": result["expectations"],
                "notes": ["Codex CLI did not expose per-run timing/token metrics through output-last-message."],
            })
    current = stats(rates["with_skill"])
    baseline = stats(rates["old_skill"])
    benchmark = {
        "metadata": {
            "skill_name": "my-novel", "skill_path": str(args.skill_root),
            "executor_model": "gpt-5.6-sol", "analyzer_model": "deterministic-token-grader",
            "timestamp": "2026-08-11T00:00:00+08:00",
            "evals_run": [item["id"] for item in evals], "runs_per_configuration": 1,
        },
        "runs": runs,
        "run_summary": {
            "with_skill": {"pass_rate": current, "time_seconds": stats([]), "tokens": stats([])},
            "old_skill": {"pass_rate": baseline, "time_seconds": stats([]), "tokens": stats([])},
            "delta": {"pass_rate": f"{current['mean'] - baseline['mean']:+.2f}",
                      "time_seconds": "n/a", "tokens": "n/a"},
        },
        "notes": [
            "Need-rewrite and skip-rewrite cases are scored separately to expose always-skip behavior.",
            "The damage-injection case requires explicit numbers/polarity failure and a new attempt.",
            "One run per configuration is a smoke benchmark; human review remains required for prose quality.",
        ],
    }
    (args.workspace / "benchmark.json").write_text(
        json.dumps(benchmark, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.workspace / "benchmark.md").write_text(
        "# MyNovel vNext vs v2.0\n\n"
        f"- vNext assertion pass rate: {current['mean']:.1%}\n"
        f"- v2.0 assertion pass rate: {baseline['mean']:.1%}\n"
        f"- delta: {current['mean'] - baseline['mean']:+.1%}\n\n"
        "Per-run timing and token counts were unavailable from Codex CLI output-last-message.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
