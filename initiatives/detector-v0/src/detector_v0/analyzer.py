"""AI analysis module — Pydantic AI + Gemini 3.1 Flash-Lite."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai import Agent, BinaryContent, RunContext

log = logging.getLogger(__name__)

SECRETS_DIR = Path.home() / ".agents" / "secrets"
GEMINI_MODEL = "google-gla:gemini-3.1-flash-lite"

SYSTEM_PROMPT = """\
You are a distraction detector. You will receive a screenshot of a user's screen
and a short audio clip from their environment.

Your job is to determine whether the user is currently engaged in distracting
content — things like social media feeds, entertainment videos, games, or
non-work browsing.

If the content IS distracting, call the `flag_distracting` tool with a brief
reason explaining why.

If the content is NOT distracting (e.g., code editor, terminal, documentation,
work-related content), do NOT call the tool — just respond briefly confirming
the content looks productive.

Be conservative: only flag things that are clearly recreational or off-task.
Ambiguous content should NOT be flagged.
"""


@dataclass
class AnalysisResult:
    """Result of a distraction analysis."""

    is_distracting: bool = False
    reason: str = ""


@dataclass
class _AnalysisDeps:
    """Mutable state passed through the agent run."""

    result: AnalysisResult = field(default_factory=AnalysisResult)


def _load_api_key() -> str:
    """Load the Google AI Studio API key from the secrets directory."""
    key_file = SECRETS_DIR / "google_ai_studio"
    if not key_file.exists():
        raise RuntimeError(
            f"Gemini API key not found at {key_file}. "
            f"Place your Google AI Studio key in {key_file}"
        )
    return key_file.read_text().strip()


def _make_agent() -> Agent[_AnalysisDeps, str]:
    """Create the Pydantic AI agent. Deferred so the API key is loaded lazily."""
    import os

    # Set the API key for the Google GenAI provider
    os.environ.setdefault("GOOGLE_API_KEY", _load_api_key())

    agent: Agent[_AnalysisDeps, str] = Agent(
        GEMINI_MODEL,
        deps_type=_AnalysisDeps,
        system_prompt=SYSTEM_PROMPT,
    )

    @agent.tool
    async def flag_distracting(ctx: RunContext[_AnalysisDeps], reason: str) -> str:
        """Flag the current screen/audio content as distracting.

        Args:
            reason: Brief explanation of why the content is distracting.
        """
        ctx.deps.result.is_distracting = True
        ctx.deps.result.reason = reason
        log.info("Content flagged as distracting: %s", reason)
        return f"Flagged as distracting: {reason}"

    return agent


# Module-level lazy singleton
_agent: Agent[_AnalysisDeps, str] | None = None


def _get_agent() -> Agent[_AnalysisDeps, str]:
    global _agent
    if _agent is None:
        _agent = _make_agent()
    return _agent


async def analyze(
    screenshot_png: bytes,
    audio_wav: bytes | None = None,
) -> AnalysisResult:
    """Analyze a screenshot (and optional audio) for distracting content.

    Args:
        screenshot_png: PNG screenshot bytes.
        audio_wav: WAV audio bytes (optional, can be None if audio capture failed).

    Returns:
        AnalysisResult with is_distracting and reason.
    """
    agent = _get_agent()
    deps = _AnalysisDeps()

    # Build multimodal user prompt
    user_prompt: list[str | BinaryContent] = [
        "Analyze this screenshot and audio for distracting content.",
        BinaryContent(data=screenshot_png, media_type="image/png"),
    ]
    if audio_wav and len(audio_wav) > 1000:
        user_prompt.append(BinaryContent(data=audio_wav, media_type="audio/wav"))

    try:
        result = await agent.run(user_prompt, deps=deps)
        log.info("Analysis complete. Distracting: %s", deps.result.is_distracting)
        if not deps.result.is_distracting:
            deps.result.reason = result.output
    except Exception as e:
        log.error("Analysis failed: %s", e)
        deps.result.reason = f"Analysis error: {e}"

    return deps.result
