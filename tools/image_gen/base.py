"""Abstract interface for image generation providers.

To add a new provider, subclass ImageGenerator and implement:
  - is_available() → bool
  - generate(prompt, negative, size, style) → Path

Everything else has a default implementation.  See docs/image_provider_spec.md
for the full specification and a worked example.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class ImageGenerator(ABC):
    """Minimal interface for image generation backends.

    Only two methods are required.  Override the rest when your provider
    needs different prompt suffixes, sizes, or negative prompts.
    """

    @property
    def name(self) -> str:
        """Human-readable provider name (e.g. 'wanx', 'sdwebui')."""
        return type(self).__module__.rsplit(".", 1)[-1]

    # ── required ───────────────────────────────────────────────

    @abstractmethod
    def generate(self, prompt: str,
                 negative: Optional[str] = None,
                 size: Optional[str] = None,
                 style: str = "scene") -> Path:
        """Generate one image and return the path to a local file.

        Args:
            prompt:   Scene description in the provider's prompt language.
            negative: Negative prompt (provider default if None).
            size:     Image dimensions (provider default if None).
            style:    One of "scene" / "combat" / "boss".

        Returns:
            Absolute path to the generated image file.  May be a temporary
            file — the caller is responsible for copying it to the final
            location.

        Raises:
            RuntimeError: Generation failed (engine will report and exit).
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider can generate images right now.

        Check for: API key present, local service reachable, dependencies
        installed, quota remaining, etc.
        """
        ...

    # ── optional overrides ─────────────────────────────────────

    def get_style_suffix(self, style: str) -> str:
        """Return a prompt suffix appended for the given style.

        Override this when your provider needs provider-specific wording
        for scene / combat / boss presets.
        """
        return ""

    def get_default_size(self) -> str:
        """Return the default image size string (e.g. '1024*1024')."""
        return "1024*1024"

    def get_default_negative(self) -> str:
        """Return the default negative prompt."""
        return ""

    # ── optional: async extension ──────────────────────────────

    # Providers MAY also implement submit() / poll() for asynchronous
    # generation (e.g. cloud APIs with task queues).  bg_generator.py
    # detects them via hasattr() — no need to override anything here.
    #
    #   def submit(self, prompt, negative=None, size=None, style="scene") -> str:
    #       '''Submit an async task. Returns task_id.'''
    #
    #   def poll(self, task_id: str) -> Optional[Path]:
    #       '''Check an async task. Returns Path when done, None if still running.'''
