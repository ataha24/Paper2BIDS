"""Data models for Paper2BIDS."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class BIDSInput(BaseModel):
    """Represents a BIDS input specification for snakebids."""

    name: str = Field(description="Name of the input (e.g., 'bold', 't1w')")
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="PyBIDS filters (suffix, extension, datatype, etc.)",
    )
    wildcards: list[str] = Field(
        default_factory=list,
        description="BIDS entities to use as wildcards",
    )


class ProcessingStep(BaseModel):
    """Represents a single processing step in the pipeline."""

    name: str = Field(description="Name of the processing step")
    description: str = Field(description="What this step does")
    inputs: list[str] = Field(description="Input file types or previous step outputs")
    outputs: list[str] = Field(description="Output file types")
    command: str | None = Field(
        default=None, description="Shell command or tool to run"
    )
    software: str | None = Field(
        default=None, description="Software package used (FSL, FreeSurfer, etc.)"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for this step"
    )


class PipelineSpecification(BaseModel):
    """Complete specification of a neuroimaging pipeline extracted from a paper."""

    title: str = Field(description="Title of the paper/pipeline")
    description: str = Field(description="Brief description of the pipeline")
    authors: list[str] = Field(default_factory=list, description="Paper authors")
    doi: str | None = Field(default=None, description="DOI of the paper")
    repository_url: str | None = Field(
        default=None, description="URL of the code repository"
    )

    # Pipeline components
    inputs: list[BIDSInput] = Field(
        default_factory=list, description="Required BIDS inputs"
    )
    steps: list[ProcessingStep] = Field(
        default_factory=list, description="Processing steps"
    )
    outputs: list[str] = Field(
        default_factory=list, description="Final output descriptions"
    )

    # Software dependencies
    software_dependencies: list[str] = Field(
        default_factory=list, description="Required software packages"
    )
    python_dependencies: list[str] = Field(
        default_factory=list, description="Python package dependencies"
    )

    # Additional metadata
    analysis_levels: list[str] = Field(
        default_factory=lambda: ["participant"],
        description="BIDS app analysis levels",
    )
    cli_parameters: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Custom CLI parameters for the app"
    )


class ExtractedCode(BaseModel):
    """Code extracted from a repository that can be used in the pipeline."""

    file_path: Path = Field(description="Original file path in the repository")
    language: str = Field(description="Programming language")
    purpose: str = Field(description="What this code does")
    code: str = Field(description="The actual code")
    dependencies: list[str] = Field(
        default_factory=list, description="Imports/dependencies"
    )
    can_be_rule: bool = Field(
        default=False, description="Whether this can become a Snakemake rule"
    )


class PaperContent(BaseModel):
    """Extracted content from a paper."""

    title: str = Field(description="Paper title")
    abstract: str = Field(default="", description="Paper abstract")
    methods_section: str = Field(default="", description="Methods section text")
    full_text: str = Field(default="", description="Full paper text")
    figures: list[str] = Field(
        default_factory=list, description="Figure captions/descriptions"
    )
    references: list[str] = Field(default_factory=list, description="Cited references")


class RepositoryContent(BaseModel):
    """Content extracted from a code repository."""

    url: str = Field(description="Repository URL")
    readme: str = Field(default="", description="README content")
    scripts: list[ExtractedCode] = Field(
        default_factory=list, description="Extracted scripts"
    )
    notebooks: list[ExtractedCode] = Field(
        default_factory=list, description="Jupyter notebooks"
    )
    config_files: dict[str, str] = Field(
        default_factory=dict, description="Configuration files"
    )
    requirements: list[str] = Field(
        default_factory=list, description="Python requirements"
    )
