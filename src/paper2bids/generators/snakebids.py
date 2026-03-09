"""Generator for creating snakebids applications."""

import shutil
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from paper2bids.models import PipelineSpecification


class SnakebidsGenerator:
    """Generate snakebids applications from pipeline specifications."""

    def __init__(self) -> None:
        """Initialize the generator with Jinja2 environment."""
        self.env = Environment(
            loader=PackageLoader("paper2bids", "templates"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(
        self,
        spec: PipelineSpecification,
        output_dir: Path,
        overwrite: bool = False,
    ) -> Path:
        """Generate a snakebids application from a pipeline specification.

        Args:
            spec: The pipeline specification to generate from.
            output_dir: Directory to create the snakebids app in.
            overwrite: Whether to overwrite existing files.

        Returns:
            Path to the generated snakebids app.
        """
        # Create output directory
        app_name = self._sanitize_name(spec.title)
        app_dir = output_dir / app_name

        if app_dir.exists():
            if overwrite:
                shutil.rmtree(app_dir)
            else:
                raise FileExistsError(
                    f"Output directory already exists: {app_dir}. "
                    "Use overwrite=True to replace."
                )

        app_dir.mkdir(parents=True)

        # Create directory structure
        (app_dir / "config").mkdir()
        (app_dir / "workflow" / "rules").mkdir(parents=True)
        (app_dir / "workflow" / "scripts").mkdir(parents=True)

        # Generate files
        self._generate_snakefile(spec, app_dir)
        self._generate_config(spec, app_dir)
        self._generate_run_py(spec, app_dir)
        self._generate_pyproject(spec, app_dir)
        self._generate_readme(spec, app_dir)

        return app_dir

    def _sanitize_name(self, title: str) -> str:
        """Convert a title to a valid directory/package name."""
        # Remove special characters and convert to snake_case
        import re

        name = title.lower()
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[-\s]+", "_", name)
        name = name.strip("_")

        # Limit length
        if len(name) > 50:
            name = name[:50].rstrip("_")

        return name or "pipeline"

    def _generate_snakefile(self, spec: PipelineSpecification, app_dir: Path) -> None:
        """Generate the Snakefile."""
        template = self.env.get_template("snakefile.jinja2")

        # Determine primary input
        primary_input = spec.inputs[0].name if spec.inputs else "input"

        content = template.render(
            title=spec.title,
            description=spec.description,
            doi=spec.doi,
            repository_url=spec.repository_url,
            inputs=spec.inputs,
            steps=spec.steps,
            primary_input=primary_input,
        )

        snakefile_path = app_dir / "workflow" / "Snakefile"
        snakefile_path.write_text(content)

    def _generate_config(self, spec: PipelineSpecification, app_dir: Path) -> None:
        """Generate the snakebids configuration file."""
        template = self.env.get_template("config.jinja2")

        content = template.render(
            title=spec.title,
            description=spec.description,
            doi=spec.doi,
            repository_url=spec.repository_url,
            inputs=spec.inputs,
            steps=spec.steps,
            analysis_levels=spec.analysis_levels,
            cli_parameters=spec.cli_parameters,
        )

        config_path = app_dir / "config" / "snakebids.yml"
        config_path.write_text(content)

    def _generate_run_py(self, spec: PipelineSpecification, app_dir: Path) -> None:
        """Generate the run.py entry point."""
        template = self.env.get_template("run_py.jinja2")

        content = template.render(
            title=spec.title,
            description=spec.description,
            doi=spec.doi,
            repository_url=spec.repository_url,
        )

        run_path = app_dir / "run.py"
        run_path.write_text(content)
        run_path.chmod(0o755)  # Make executable

    def _generate_pyproject(self, spec: PipelineSpecification, app_dir: Path) -> None:
        """Generate pyproject.toml for the snakebids app."""
        app_name = self._sanitize_name(spec.title)

        # Build dependencies list
        deps = ["snakebids>=0.10", "pybids>=0.15", "nibabel>=4.0"]
        deps.extend(spec.python_dependencies)
        deps = list(set(deps))  # Remove duplicates

        content = f'''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{app_name}"
version = "0.1.0"
description = "{spec.description}"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
{self._format_deps(deps)}
]

[project.scripts]
{app_name} = "run:app.run"

[tool.hatch.build.targets.wheel]
packages = ["workflow"]
'''
        pyproject_path = app_dir / "pyproject.toml"
        pyproject_path.write_text(content)

    def _generate_readme(self, spec: PipelineSpecification, app_dir: Path) -> None:
        """Generate README.md for the snakebids app."""
        steps_list = "\n".join(
            f"1. **{step.name}**: {step.description}" for step in spec.steps
        )

        software_list = ", ".join(spec.software_dependencies) or "None specified"

        content = f"""# {spec.title}

{spec.description}

## Generated by Paper2BIDS

This snakebids application was automatically generated from a neuroimaging paper.

{"**DOI:** " + spec.doi if spec.doi else ""}
{"**Repository:** " + spec.repository_url if spec.repository_url else ""}

## Installation

```bash
pip install -e .
```

## Usage

```bash
./run.py /path/to/bids/dataset /path/to/output participant
```

Or with Snakemake directly:

```bash
snakemake --cores all --config bids_dir=/path/to/bids
```

## Pipeline Steps

{steps_list}

## Software Dependencies

{software_list}

## BIDS Inputs

This pipeline expects the following BIDS data:

| Input | Suffix | Datatype |
|-------|--------|----------|
{self._format_inputs_table(spec.inputs)}

## Configuration

See `config/snakebids.yml` for all configuration options.

## License

Please refer to the original paper and repository for licensing information.
"""
        readme_path = app_dir / "README.md"
        readme_path.write_text(content)

    def _format_deps(self, deps: list[str]) -> str:
        """Format dependencies for pyproject.toml."""
        return ",\n".join(f'    "{dep}"' for dep in sorted(deps))

    def _format_inputs_table(self, inputs: list) -> str:
        """Format inputs as a markdown table."""
        rows = []
        for inp in inputs:
            suffix = inp.filters.get("suffix", "")
            datatype = inp.filters.get("datatype", "")
            rows.append(f"| {inp.name} | {suffix} | {datatype} |")
        return "\n".join(rows)
