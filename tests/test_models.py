"""Tests for data models."""

import pytest
from pydantic import ValidationError

from paper2bids.models import (
    BIDSInput,
    ProcessingStep,
    PipelineSpecification,
    ExtractedCode,
    PaperContent,
)


class TestBIDSInput:
    """Tests for BIDSInput model."""

    def test_basic_creation(self):
        """Test creating a basic BIDS input."""
        inp = BIDSInput(
            name="bold",
            filters={"suffix": "bold", "extension": ".nii.gz"},
            wildcards=["subject", "session"],
        )
        assert inp.name == "bold"
        assert inp.filters["suffix"] == "bold"
        assert "subject" in inp.wildcards

    def test_default_values(self):
        """Test default values for optional fields."""
        inp = BIDSInput(name="t1w")
        assert inp.filters == {}
        assert inp.wildcards == []


class TestProcessingStep:
    """Tests for ProcessingStep model."""

    def test_full_step(self):
        """Test creating a complete processing step."""
        step = ProcessingStep(
            name="motion_correction",
            description="Correct for head motion",
            inputs=["bold"],
            outputs=["bold_mc"],
            command="mcflirt -in {input} -out {output}",
            software="FSL",
            parameters={"cost": "mutualinfo"},
        )
        assert step.name == "motion_correction"
        assert step.software == "FSL"
        assert step.parameters["cost"] == "mutualinfo"

    def test_minimal_step(self):
        """Test creating a minimal processing step."""
        step = ProcessingStep(
            name="smooth",
            description="Spatial smoothing",
            inputs=["bold"],
            outputs=["bold_smooth"],
        )
        assert step.command is None
        assert step.software is None
        assert step.parameters == {}


class TestPipelineSpecification:
    """Tests for PipelineSpecification model."""

    def test_full_specification(self):
        """Test creating a complete pipeline specification."""
        spec = PipelineSpecification(
            title="My Pipeline",
            description="A test pipeline",
            authors=["Author One", "Author Two"],
            doi="10.1234/test",
            inputs=[
                BIDSInput(
                    name="bold",
                    filters={"suffix": "bold"},
                    wildcards=["subject"],
                )
            ],
            steps=[
                ProcessingStep(
                    name="preprocess",
                    description="Preprocessing",
                    inputs=["bold"],
                    outputs=["bold_preproc"],
                )
            ],
            software_dependencies=["FSL", "FreeSurfer"],
        )
        assert spec.title == "My Pipeline"
        assert len(spec.inputs) == 1
        assert len(spec.steps) == 1
        assert "FSL" in spec.software_dependencies

    def test_default_analysis_levels(self):
        """Test default analysis levels."""
        spec = PipelineSpecification(
            title="Test",
            description="Test pipeline",
        )
        assert "participant" in spec.analysis_levels


class TestExtractedCode:
    """Tests for ExtractedCode model."""

    def test_code_extraction(self):
        """Test extracted code model."""
        from pathlib import Path

        code = ExtractedCode(
            file_path=Path("scripts/preprocess.py"),
            language="python",
            purpose="Preprocessing script",
            code="import nibabel as nib\nprint('hello')",
            dependencies=["nibabel"],
            can_be_rule=True,
        )
        assert code.language == "python"
        assert code.can_be_rule is True
        assert "nibabel" in code.dependencies


class TestPaperContent:
    """Tests for PaperContent model."""

    def test_paper_content(self):
        """Test paper content model."""
        content = PaperContent(
            title="Test Paper",
            abstract="This is the abstract",
            methods_section="We used FSL...",
            full_text="Full paper text here",
        )
        assert content.title == "Test Paper"
        assert "abstract" in content.abstract.lower()
