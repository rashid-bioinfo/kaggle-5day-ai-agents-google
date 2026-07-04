"""Local fallback grader for generated expense traces.

This uses the same LLM-as-judge metric functions configured for agents-cli,
but avoids the Vertex/ADC dependency in the current agents-cli grade path.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from statistics import mean
from typing import Any

from dotenv import load_dotenv


DEFAULT_TRACES = Path("artifacts/traces/generated_traces.json")
DEFAULT_OUTPUT = Path("artifacts/grade_results/local_results.json")
METRICS = {
    "routing_correctness": Path("tests/eval/metrics_routing.py"),
    "security_containment": Path("tests/eval/metrics_security.py"),
}


def _load_metric(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load metric file: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate


def _print_table(results: dict[str, Any]) -> None:
    print("\nEvaluation Summary")
    print("metric                 avg_score")
    print("--------------------   ---------")
    for metric_name, summary in results["summary"].items():
        print(f"{metric_name:<22} {summary['avg_score']:.2f}")

    print("\nPer-case Results")
    print("case_id                                      routing  security")
    print("------------------------------------------   -------  --------")
    for case in results["cases"]:
        routing = case["metrics"]["routing_correctness"]["score"]
        security = case["metrics"]["security_containment"]["score"]
        print(f"{case['eval_case_id']:<44} {routing:<7}  {security:<8}")

    print("\nPer-case Explanations")
    for case in results["cases"]:
        print(f"\n{case['eval_case_id']}")
        for metric_name, metric_result in case["metrics"].items():
            print(
                f"  {metric_name}: {metric_result['score']} - "
                f"{metric_result['explanation']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    load_dotenv(".env")
    traces = json.loads(args.traces.read_text())
    evaluators = {name: _load_metric(path) for name, path in METRICS.items()}
    case_results = []

    for case in traces["eval_cases"]:
        metric_results = {}
        for metric_name, evaluate in evaluators.items():
            metric_results[metric_name] = evaluate(case)
        case_results.append(
            {
                "eval_case_id": case["eval_case_id"],
                "expected": case.get("expected", {}),
                "metrics": metric_results,
            }
        )

    summary = {}
    for metric_name in evaluators:
        scores = [
            case["metrics"][metric_name]["score"] for case in case_results
        ]
        summary[metric_name] = {"avg_score": mean(scores), "case_count": len(scores)}

    results = {"summary": summary, "cases": case_results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2))
    _print_table(results)
    print(f"\nSaved local grade results to {args.output}")


if __name__ == "__main__":
    main()
