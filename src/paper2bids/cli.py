"""Command-line interface for Paper2BIDS."""

import os
from pathlib import Path

import click
from rich.console import Console

from paper2bids import __version__
from paper2bids.core import Paper2BIDS


console = Console()


@click.group()
@click.version_option(version=__version__)
def main():
    """Paper2BIDS: Transform neuroimaging papers into snakebids applications.

    Convert academic papers and their associated code repositories into
    reproducible snakebids applications that follow BIDS standards.
    """
    pass


@main.command()
@click.argument("paper", type=click.Path(exists=True, path_type=Path), required=False)
@click.option(
    "--paper-url",
    type=str,
    help="URL to download the paper PDF from",
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, path_type=Path),
    help="Local path to the code repository",
)
@click.option(
    "--repo-url",
    type=str,
    help="URL of the git repository (will be cloned)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Output directory for the generated snakebids app",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite existing output directory",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress progress output",
)
def convert(
    paper: Path | None,
    paper_url: str | None,
    repo: Path | None,
    repo_url: str | None,
    output: Path,
    overwrite: bool,
    api_key: str | None,
    quiet: bool,
):
    """Convert a paper and/or repository to a snakebids application.

    PAPER is an optional path to the paper PDF file.

    Examples:

        # From paper only
        paper2bids convert paper.pdf -o ./output

        # From repository only
        paper2bids convert --repo-url https://github.com/user/repo -o ./output

        # From both paper and repository
        paper2bids convert paper.pdf --repo-url https://github.com/user/repo

        # From paper URL and local repository
        paper2bids convert --paper-url https://arxiv.org/pdf/xxx --repo ./my-repo
    """
    if not paper and not paper_url and not repo and not repo_url:
        raise click.UsageError(
            "Please provide at least one input: "
            "PAPER, --paper-url, --repo, or --repo-url"
        )

    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise click.UsageError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment "
                "variable or use --api-key option."
            )

    try:
        converter = Paper2BIDS(api_key=api_key, verbose=not quiet)
        app_path = converter.convert(
            paper_path=paper,
            paper_url=paper_url,
            repo_path=repo,
            repo_url=repo_url,
            output_dir=output,
            overwrite=overwrite,
        )

        if quiet:
            click.echo(str(app_path))

    except FileExistsError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("Use --overwrite to replace existing directory.")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@main.command()
@click.argument("repo_url", type=str)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Output directory",
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing output")
@click.option("--api-key", envvar="ANTHROPIC_API_KEY", help="Anthropic API key")
def from_repo(repo_url: str, output: Path, overwrite: bool, api_key: str | None):
    """Generate a snakebids app from a GitHub repository.

    This analyzes the repository code to understand the processing pipeline
    and generates a snakebids application.

    Example:

        paper2bids from-repo https://github.com/nilearn/nilearn
    """
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise click.UsageError("Anthropic API key required.")

    try:
        converter = Paper2BIDS(api_key=api_key)
        converter.from_repository(repo_url, output_dir=output, overwrite=overwrite)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@main.command()
@click.argument("paper", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Output directory",
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing output")
@click.option("--api-key", envvar="ANTHROPIC_API_KEY", help="Anthropic API key")
def from_paper(paper: Path, output: Path, overwrite: bool, api_key: str | None):
    """Generate a snakebids app from a paper PDF.

    This extracts the methodology from the paper and generates a skeleton
    snakebids application that you can then customize.

    Example:

        paper2bids from-paper paper.pdf -o ./output
    """
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise click.UsageError("Anthropic API key required.")

    try:
        converter = Paper2BIDS(api_key=api_key)
        converter.from_paper(paper, output_dir=output, overwrite=overwrite)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@main.command()
def info():
    """Show information about Paper2BIDS."""
    console.print(f"[bold]Paper2BIDS[/bold] v{__version__}")
    console.print()
    console.print(
        "Transform neuroimaging papers and code into reproducible "
        "snakebids applications."
    )
    console.print()
    console.print("[bold]How it works:[/bold]")
    console.print("  1. Parse paper PDF to extract methodology")
    console.print("  2. Clone and analyze code repository")
    console.print("  3. Use Claude to understand the pipeline")
    console.print("  4. Generate a complete snakebids application")
    console.print()
    console.print("[bold]Resources:[/bold]")
    console.print("  Snakebids: https://github.com/khanlab/snakebids")
    console.print("  BIDS: https://bids.neuroimaging.io")
    console.print()
    console.print("[bold]Environment Variables:[/bold]")
    console.print("  ANTHROPIC_API_KEY - Required for LLM analysis")


if __name__ == "__main__":
    main()
