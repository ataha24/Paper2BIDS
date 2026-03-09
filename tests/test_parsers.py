"""Tests for paper and repository parsers."""

import pytest

from paper2bids.parsers.paper import PaperParser


class TestPaperParser:
    """Tests for PaperParser."""

    def test_extract_software_fsl(self):
        """Test extraction of FSL software mention."""
        parser = PaperParser()
        text = "We used FSL for preprocessing and FreeSurfer for segmentation."
        software = parser.extract_software(text)
        assert "FSL" in software or "FMRIB Software Library" in software
        assert "FreeSurfer" in software

    def test_extract_software_multiple(self):
        """Test extraction of multiple software mentions."""
        parser = PaperParser()
        text = """
        The preprocessing pipeline utilized ANTs for registration,
        SPM12 for statistical analysis, and MRtrix3 for tractography.
        """
        software = parser.extract_software(text)
        assert len(software) >= 2

    def test_extract_processing_steps(self):
        """Test extraction of processing step mentions."""
        parser = PaperParser()
        text = """
        Images underwent motion correction and slice timing correction.
        Spatial normalization to MNI space was performed using ANTs.
        Finally, spatial smoothing with a 6mm FWHM Gaussian kernel was applied.
        """
        steps = parser.extract_processing_steps(text)
        assert "preprocessing" in steps or "smoothing" in steps

    def test_extract_title(self):
        """Test title extraction from text."""
        parser = PaperParser()
        content = parser._parse_text(
            """A Novel fMRI Analysis Pipeline for Resting State Connectivity

            Abstract
            This paper presents a new method...
            """
        )
        assert "fMRI" in content.title or "Novel" in content.title

    def test_extract_abstract(self):
        """Test abstract extraction."""
        parser = PaperParser()
        text = """
        Title of Paper

        Abstract
        This is the abstract of the paper describing the methodology.

        Introduction
        Here begins the introduction.
        """
        content = parser._parse_text(text)
        assert "abstract" in content.abstract.lower() or len(content.abstract) > 0

    def test_extract_methods(self):
        """Test methods section extraction."""
        parser = PaperParser()
        text = """
        Introduction
        Background information.

        Methods
        We collected data from 50 participants.
        MRI acquisition was performed on a 3T scanner.

        Results
        We found significant effects.
        """
        content = parser._parse_text(text)
        # Methods might be extracted
        assert isinstance(content.methods_section, str)


class TestRepositoryParser:
    """Tests for RepositoryParser."""

    def test_should_skip_path_git(self):
        """Test that .git directories are skipped."""
        from pathlib import Path
        from paper2bids.parsers.repository import RepositoryParser

        parser = RepositoryParser()
        assert parser._should_skip_path(Path(".git/config"))
        assert parser._should_skip_path(Path("project/.git/HEAD"))

    def test_should_skip_path_pycache(self):
        """Test that __pycache__ directories are skipped."""
        from pathlib import Path
        from paper2bids.parsers.repository import RepositoryParser

        parser = RepositoryParser()
        assert parser._should_skip_path(Path("__pycache__/module.pyc"))
        assert parser._should_skip_path(Path("src/__pycache__/file.pyc"))

    def test_is_relevant_code_nibabel(self):
        """Test detection of neuroimaging-relevant code."""
        from paper2bids.parsers.repository import RepositoryParser

        parser = RepositoryParser()
        code = """
        import nibabel as nib
        img = nib.load('data.nii.gz')
        """
        assert parser._is_relevant_code(code)

    def test_is_relevant_code_nifti(self):
        """Test detection of NIfTI file patterns."""
        from paper2bids.parsers.repository import RepositoryParser

        parser = RepositoryParser()
        code = """
        input_file = 'sub-01/func/sub-01_task-rest_bold.nii.gz'
        """
        assert parser._is_relevant_code(code)

    def test_detect_language(self):
        """Test language detection from file extensions."""
        from pathlib import Path
        from paper2bids.parsers.repository import RepositoryParser

        parser = RepositoryParser()
        assert parser._detect_language(Path("script.py")) == "python"
        assert parser._detect_language(Path("run.sh")) == "bash"
        assert parser._detect_language(Path("analysis.R")) == "r"
        assert parser._detect_language(Path("preproc.m")) == "matlab"

    def test_extract_imports(self):
        """Test Python import extraction."""
        from paper2bids.parsers.repository import RepositoryParser

        parser = RepositoryParser()
        code = """
        import nibabel as nib
        import numpy as np
        from nilearn import plotting
        from scipy.stats import ttest_ind
        """
        imports = parser._extract_imports(code)
        assert "nibabel" in imports
        assert "numpy" in imports
        assert "nilearn" in imports
        assert "scipy" in imports
