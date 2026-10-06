"""The LLM layer (openspec: llm-layer). Every LLM and decision-model call in
the backend goes through here, addressed by a logical route — services
never name a model and never call a provider SDK directly."""

from .agents import override_route, run_structured
from .usage import UsageContext

__all__ = ["UsageContext", "override_route", "run_structured"]
