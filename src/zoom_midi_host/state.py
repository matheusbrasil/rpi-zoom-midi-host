"""Domain models representing pedal state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class Effect:
    """Represents a single Zoom effect block."""

    slot: int
    name: str
    enabled: bool = True
    icon_slug: Optional[str] = None


@dataclass_json
@dataclass
class PatchChain:
    """Represents the chain of effects currently loaded on the pedal."""

    patch_name: str
    effects: List[Effect] = field(default_factory=list)

    def active_effects(self, skip_first: bool = True, only_enabled: bool = True) -> List[Effect]:
        """Return the list of effects, optionally filtering by enablement and slot."""

        effects: List[Effect] = self.effects
        if only_enabled:
            effects = [effect for effect in effects if effect.enabled]
        if skip_first:
            effects = [effect for effect in effects if effect.slot != 0]
        return effects


@dataclass_json
@dataclass
class FootswitchAction:
    """Action triggered by an external controller footswitch."""

    midi_note: int
    description: str
    command: str
    argument: Optional[int] = None
