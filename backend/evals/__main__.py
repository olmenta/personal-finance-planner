"""Run an eval suite: `uv run python -m evals <onboarding|category_suggestions> [--model MODEL]`.

--model overrides the suite's route model for this run (baseline comparisons,
e.g. --model anthropic:claude-sonnet-4-6). Results print as a table and, with
LOGFIRE_TOKEN set, appear in Logfire as an experiment.
"""

import argparse

from . import category_suggestions, onboarding
from .common import require_key, setup_observability, use_model

SUITES = {
    "onboarding": ("onboarding", onboarding),
    "category_suggestions": ("category_suggestions", category_suggestions),
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m evals")
    parser.add_argument("suite", choices=sorted(SUITES))
    parser.add_argument("--model", help="override the route's model, e.g. anthropic:claude-sonnet-4-6")
    args = parser.parse_args()

    route, module = SUITES[args.suite]
    use_model(route, args.model)
    require_key()
    setup_observability()
    report = module.dataset().evaluate_sync(
        module.task, name=f"{args.suite}:{args.model or 'default'}", max_concurrency=4
    )
    report.print(include_input=False, include_output=True)


if __name__ == "__main__":
    main()
