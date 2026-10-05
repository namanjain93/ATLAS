"""Load, validate, and fingerprint the Constitution, operating config and instruments."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from atlas.config.models import AtlasConfig, ConfigError, Constitution
from atlas.domain.enums import Provenance
from atlas.domain.schemas import InstrumentSpec


def _read_toml(path: Path) -> dict:
    if not path.is_file():
        raise ConfigError(f"missing config file: {path}")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


class InstrumentRegistry:
    """Instrument specs by symbol. Synthetic specs are included only when permitted."""

    def __init__(self, specs: list[InstrumentSpec]):
        by_symbol: dict[str, InstrumentSpec] = {}
        for s in specs:
            if s.symbol in by_symbol:
                raise ConfigError(f"duplicate instrument symbol {s.symbol}")
            by_symbol[s.symbol] = s
        self._specs = by_symbol

    def get(self, symbol: str) -> InstrumentSpec | None:
        return self._specs.get(symbol)

    def all(self) -> list[InstrumentSpec]:
        return list(self._specs.values())


@dataclass(frozen=True)
class LoadedConfig:
    root: Path
    constitution: Constitution
    config: AtlasConfig
    instruments: InstrumentRegistry
    fingerprint: str  # sha256 over constitution + config + instrument specs

    @property
    def version_label(self) -> str:
        return f"cfg-{self.config.config_version}/const-{self.constitution.version}"


def load_config(root: Path | str, config_dir: str = "config") -> LoadedConfig:
    root = Path(root).resolve()
    cdir = root / config_dir
    try:
        constitution = Constitution.model_validate(_read_toml(cdir / "constitution.toml"))
        config = AtlasConfig.model_validate(_read_toml(cdir / "atlas.toml"))
    except ValidationError as exc:
        raise ConfigError(f"invalid configuration: {exc}") from exc
    config.check_against(constitution)

    specs: list[InstrumentSpec] = []
    files = list(config.instruments.files)
    synthetic_files = list(config.instruments.synthetic_files) if config.synthetic_allowed else []
    for rel in files + synthetic_files:
        data = _read_toml(root / rel)
        for raw in data.get("instrument", []):
            try:
                spec = InstrumentSpec.model_validate(raw)
            except ValidationError as exc:
                raise ConfigError(f"invalid instrument in {rel}: {exc}") from exc
            is_synth_file = rel in synthetic_files
            if is_synth_file and spec.provenance is not Provenance.SYNTHETIC:
                raise ConfigError(f"{rel}: synthetic file contains non-SYNTHETIC spec {spec.symbol}")
            if not is_synth_file and spec.provenance is Provenance.SYNTHETIC:
                raise ConfigError(f"{rel}: SYNTHETIC spec {spec.symbol} outside a synthetic file")
            specs.append(spec)
    registry = InstrumentRegistry(specs)

    fingerprint = hashlib.sha256(
        canonical_json(
            {
                "constitution": constitution.model_dump(mode="json"),
                "config": config.model_dump(mode="json"),
                "instruments": sorted(
                    (s.model_dump(mode="json") for s in registry.all()), key=lambda d: d["symbol"]
                ),
            }
        ).encode()
    ).hexdigest()
    return LoadedConfig(root, constitution, config, registry, fingerprint)
