from __future__ import annotations

import typer

app = typer.Typer(help="ADME platform CLI")


@app.command()
def seed(seed: int = 42) -> None:
    from adme_platform.api.store import STORE
    from data_generation.generator import generate_platform

    STORE.platform = generate_platform(seed=seed)
    STORE.platform.to_files(STORE.data_dir)
    STORE._build_lineage()
    typer.echo(f"Seeded synthetic platform seed={seed}")


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run("adme_platform.api.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    app()
