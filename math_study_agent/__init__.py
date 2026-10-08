"""Math Study Agent System.

Turns lecture slides and professor notes into intuitive, conceptual study
notes using four agents (Material Analyst, Concept Mapper, Intuition Teacher,
Note Editor) coordinated by an Orchestrator over versioned JSON schemas.
"""

from .errors import AgentError, LLMError, MathStudyError, PipelineError, SchemaValidationError
from .ingest import build_bundle, load_source
from .orchestrator import Orchestrator, OrchestratorConfig, PipelineResult

__version__ = "0.1.0"

__all__ = [
    "AgentError",
    "LLMError",
    "MathStudyError",
    "Orchestrator",
    "OrchestratorConfig",
    "PipelineError",
    "PipelineResult",
    "SchemaValidationError",
    "build_bundle",
    "load_source",
]
