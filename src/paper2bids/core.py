"""Core Paper2BIDS class that orchestrates the conversion process."""

from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from paper2bids.analyzers.code import CodeAnalyzer
from paper2bids.analyzers.methodology import MethodologyAnalyzer
from paper2bids.generators.snakebids import SnakebidsGenerator
from paper2bids.models import PipelineSpecification
from paper2bids.parsers.paper import PaperParser
from paper2bids.parsers.repository import RepositoryParser


class Paper2BIDS:
    """Main class for converting papers to snakebids applications."""

    def __init__(self, api_key: str | None = None, verbose: bool = True) -> None:
        """Initialize Paper2BIDS.

        Args:
            api_key: Anthropic API key for LLM analysis.
            verbose: Whether to print progress information.
        """
        self.api_key = api_key
        self.verbose = verbose
        self.console = Console()

        # Initialize components
        self.paper_parser = PaperParser()
        self.repo_parser = RepositoryParser()
        self.methodology_analyzer = MethodologyAnalyzer(api_key=api_key)
        self.code_analyzer = CodeAnalyzer(api_key=api_key)
        self.generator = SnakebidsGenerator()

    def convert(
        self,
        paper_path: Path | None = None,
        paper_url: str | None = None,
        repo_path: Path | None = None,
        repo_url: str | None = None,
        output_dir: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Convert a paper and its code to a snakebids application.

        Args:
            paper_path: Local path to the paper PDF.
            paper_url: URL to download the paper from.
            repo_path: Local path to the code repository.
            repo_url: URL of the git repository.
            output_dir: Directory to output the snakebids app.
            overwrite: Whether to overwrite existing output.

        Returns:
            Path to the generated snakebids application.
        """
        if output_dir is None:
            output_dir = Path.cwd()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            disable=not self.verbose,
        ) as progress:
            # Step 1: Parse paper
            spec = None
            if paper_path or paper_url:
                task = progress.add_task("Parsing paper...", total=None)
                paper_content = self._parse_paper(paper_path, paper_url)
                progress.update(task, completed=True)

                # Step 2: Analyze methodology
                task = progress.add_task("Analyzing methodology...", total=None)
                spec = self.methodology_analyzer.analyze(paper_content)
                progress.update(task, completed=True)

            # Step 3: Parse repository
            repo_content = None
            if repo_path or repo_url:
                task = progress.add_task("Parsing repository...", total=None)
                repo_content = self._parse_repository(repo_path, repo_url)
                if spec:
                    spec.repository_url = repo_url or str(repo_path)
                progress.update(task, completed=True)

                # Step 4: Analyze code
                task = progress.add_task("Analyzing code...", total=None)
                code_steps = self.code_analyzer.analyze_repository(repo_content)
                progress.update(task, completed=True)

                # Step 5: Merge steps
                if spec and code_steps:
                    task = progress.add_task("Merging pipeline steps...", total=None)
                    spec.steps = self.code_analyzer.merge_steps(spec.steps, code_steps)
                    progress.update(task, completed=True)
                elif code_steps and not spec:
                    # Create spec from code only
                    spec = PipelineSpecification(
                        title=repo_content.readme.split("\n")[0][:100]
                        if repo_content.readme
                        else "Pipeline",
                        description="Pipeline generated from code repository",
                        repository_url=repo_url or str(repo_path),
                        steps=code_steps,
                        python_dependencies=repo_content.requirements,
                    )

            if spec is None:
                raise ValueError(
                    "No paper or repository provided. "
                    "Please provide at least one input source."
                )

            # Step 6: Generate snakebids app
            task = progress.add_task("Generating snakebids app...", total=None)
            app_path = self.generator.generate(spec, output_dir, overwrite=overwrite)
            progress.update(task, completed=True)

        if self.verbose:
            self.console.print(f"\n[green]Success![/green] Generated snakebids app at:")
            self.console.print(f"  [bold]{app_path}[/bold]")
            self.console.print("\nNext steps:")
            self.console.print(f"  1. cd {app_path}")
            self.console.print("  2. Review and customize the generated files")
            self.console.print("  3. pip install -e .")
            self.console.print(
                "  4. ./run.py /path/to/bids /path/to/output participant"
            )

        return app_path

    def _parse_paper(
        self, paper_path: Path | None, paper_url: str | None
    ):
        """Parse paper from path or URL."""
        if paper_path:
            if not paper_path.exists():
                raise FileNotFoundError(f"Paper not found: {paper_path}")

            if paper_path.suffix.lower() == ".pdf":
                return self.paper_parser.parse_pdf(paper_path)
            else:
                text = paper_path.read_text()
                return self.paper_parser.parse_text(text)

        elif paper_url:
            # Download and parse
            import tempfile
            import httpx

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                response = httpx.get(paper_url, follow_redirects=True)
                response.raise_for_status()
                f.write(response.content)
                temp_path = Path(f.name)

            try:
                return self.paper_parser.parse_pdf(temp_path)
            finally:
                temp_path.unlink()

        raise ValueError("No paper path or URL provided")

    def _parse_repository(
        self, repo_path: Path | None, repo_url: str | None
    ):
        """Parse repository from path or URL."""
        if repo_path:
            return self.repo_parser.parse_local(repo_path)
        elif repo_url:
            return self.repo_parser.parse_remote(repo_url)

        raise ValueError("No repository path or URL provided")

    def from_paper(
        self,
        paper_path: Path,
        output_dir: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Convert from paper only.

        Args:
            paper_path: Path to the paper PDF.
            output_dir: Output directory.
            overwrite: Whether to overwrite existing output.

        Returns:
            Path to generated snakebids app.
        """
        return self.convert(
            paper_path=paper_path,
            output_dir=output_dir,
            overwrite=overwrite,
        )

    def from_repository(
        self,
        repo_url: str,
        output_dir: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Convert from repository only.

        Args:
            repo_url: URL of the git repository.
            output_dir: Output directory.
            overwrite: Whether to overwrite existing output.

        Returns:
            Path to generated snakebids app.
        """
        return self.convert(
            repo_url=repo_url,
            output_dir=output_dir,
            overwrite=overwrite,
        )

    def from_paper_and_repo(
        self,
        paper_path: Path,
        repo_url: str,
        output_dir: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Convert from both paper and repository.

        Args:
            paper_path: Path to the paper PDF.
            repo_url: URL of the git repository.
            output_dir: Output directory.
            overwrite: Whether to overwrite existing output.

        Returns:
            Path to generated snakebids app.
        """
        return self.convert(
            paper_path=paper_path,
            repo_url=repo_url,
            output_dir=output_dir,
            overwrite=overwrite,
        )
