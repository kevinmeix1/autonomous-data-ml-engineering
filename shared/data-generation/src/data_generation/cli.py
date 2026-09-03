from __future__ import annotations

import json
from pathlib import Path

import typer

from data_generation.generator import generate_platform

app = typer.Typer(help="Synthetic insurance platform data generator")


@app.command()
def generate(
    seed: int = typer.Option(42),
    output: Path = typer.Option(Path("data/synthetic")),
    incidents: int = typer.Option(40),
) -> None:
    platform = generate_platform(seed=seed, n_incidents=incidents)
    platform.to_files(output)
    scenarios_path = Path("benchmarks/scenarios.json")
    scenarios_path.parent.mkdir(parents=True, exist_ok=True)
    scenarios_path.write_text(json.dumps({"scenarios": platform.scenarios}, indent=2))
    typer.echo(f"Wrote synthetic platform to {output} ({len(platform.incidents)} incidents)")


if __name__ == "__main__":
    app()
