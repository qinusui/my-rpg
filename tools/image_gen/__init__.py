"""Image generation provider factory.

Reads config.json to determine the active provider, dynamically imports
the corresponding module, and returns a Provider instance.

Usage:
    from image_gen import get_generator
    gen = get_generator()           # uses config.json provider
    gen = get_generator("wanx")     # explicit provider name

To add a new provider, drop a file in this directory and set config.json.
See docs/image_provider_spec.md for the full specification.
"""

import json
import os
from typing import Optional

from .base import ImageGenerator

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(ROOT, "config.json")


def _load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_generator(provider_name: Optional[str] = None) -> ImageGenerator:
    """Return the active ImageGenerator.

    Resolution order:
    1. Explicit provider_name argument
    2. config.json image_gen.provider
    3. Default: "wanx"

    If the primary provider is unavailable and a fallback is configured,
    the fallback is tried automatically.
    """
    cfg = _load_config()
    ig_cfg = cfg.get("image_gen", {})

    primary = provider_name or ig_cfg.get("provider", "wanx")
    fallback = ig_cfg.get("fallback") if not provider_name else None

    # Try primary
    gen = _try_load(primary)
    if gen is not None and gen.is_available():
        return gen

    # Try fallback
    if fallback and fallback != primary:
        gen = _try_load(fallback)
        if gen is not None and gen.is_available():
            return gen

    # Return primary even if unavailable — caller gets a clear error
    gen = _try_load(primary)
    if gen is not None:
        return gen
    raise ImportError(f"Unknown image_gen provider: {primary}")


def _try_load(name: str) -> Optional[ImageGenerator]:
    """Dynamically import image_gen.{name} and return its Provider instance.

    Returns None if the module doesn't exist or cannot be imported.
    """
    try:
        mod = __import__(f"image_gen.{name}", fromlist=["Provider"])
        cls = getattr(mod, "Provider")
        return cls()
    except (ImportError, AttributeError):
        return None


def list_providers():
    """Print the active provider for debugging.  Does NOT scan filesystem."""
    cfg = _load_config()
    ig_cfg = cfg.get("image_gen", {})
    active = ig_cfg.get("provider", "wanx")

    gen = get_generator()
    status = "available" if gen.is_available() else "unavailable"
    print(f"  {active}: {status} ← active")

    fallback = ig_cfg.get("fallback")
    if fallback:
        fb_gen = _try_load(fallback)
        fb_status = "available" if (fb_gen and fb_gen.is_available()) else "unavailable"
        print(f"  {fallback}: {fb_status} (fallback)")


if __name__ == "__main__":
    list_providers()
