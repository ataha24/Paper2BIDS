"""Parser for extracting code and information from repositories."""

import re
import tempfile
from pathlib import Path

import git

from paper2bids.models import ExtractedCode, RepositoryContent


class RepositoryParser:
    """Parse code repositories to extract scripts and configuration."""

    # File patterns to look for
    SCRIPT_PATTERNS = ["*.py", "*.sh", "*.bash", "*.m", "*.R"]
    NOTEBOOK_PATTERNS = ["*.ipynb"]
    CONFIG_PATTERNS = [
        "requirements.txt",
        "setup.py",
        "pyproject.toml",
        "environment.yml",
        "environment.yaml",
        "Dockerfile",
        "*.cfg",
        "config.yaml",
        "config.yml",
    ]
    README_PATTERNS = ["README.md", "README.rst", "README.txt", "README"]

    # Patterns indicating neuroimaging code
    NEUROIMAGING_IMPORTS = [
        "nibabel",
        "nilearn",
        "nipype",
        "fsl",
        "freesurfer",
        "ants",
        "mne",
        "dipy",
        "pybids",
        "bids",
    ]

    def __init__(self) -> None:
        """Initialize the repository parser."""
        pass

    def parse_local(self, repo_path: Path) -> RepositoryContent:
        """Parse a local repository directory.

        Args:
            repo_path: Path to the local repository.

        Returns:
            RepositoryContent with extracted information.
        """
        if not repo_path.is_dir():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        return self._parse_directory(repo_path)

    def parse_remote(self, url: str) -> RepositoryContent:
        """Clone and parse a remote repository.

        Args:
            url: URL of the git repository.

        Returns:
            RepositoryContent with extracted information.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            git.Repo.clone_from(url, repo_path, depth=1)
            content = self._parse_directory(repo_path)
            content.url = url
            return content

    def _parse_directory(self, repo_path: Path) -> RepositoryContent:
        """Parse a directory and extract relevant content.

        Args:
            repo_path: Path to the repository directory.

        Returns:
            RepositoryContent with extracted information.
        """
        readme = self._find_readme(repo_path)
        scripts = self._find_scripts(repo_path)
        notebooks = self._find_notebooks(repo_path)
        config_files = self._find_config_files(repo_path)
        requirements = self._extract_requirements(repo_path, config_files)

        return RepositoryContent(
            url=str(repo_path),
            readme=readme,
            scripts=scripts,
            notebooks=notebooks,
            config_files=config_files,
            requirements=requirements,
        )

    def _find_readme(self, repo_path: Path) -> str:
        """Find and read the README file."""
        for pattern in self.README_PATTERNS:
            matches = list(repo_path.glob(pattern))
            if matches:
                try:
                    return matches[0].read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
        return ""

    def _find_scripts(self, repo_path: Path) -> list[ExtractedCode]:
        """Find and parse script files."""
        scripts = []

        for pattern in self.SCRIPT_PATTERNS:
            for file_path in repo_path.rglob(pattern):
                # Skip hidden directories and common non-essential paths
                if self._should_skip_path(file_path):
                    continue

                try:
                    code = file_path.read_text(encoding="utf-8", errors="ignore")
                    if self._is_relevant_code(code):
                        extracted = self._extract_code_info(file_path, code)
                        scripts.append(extracted)
                except Exception:
                    continue

        return scripts

    def _find_notebooks(self, repo_path: Path) -> list[ExtractedCode]:
        """Find and parse Jupyter notebooks."""
        import json

        notebooks = []

        for pattern in self.NOTEBOOK_PATTERNS:
            for file_path in repo_path.rglob(pattern):
                if self._should_skip_path(file_path):
                    continue

                try:
                    content = json.loads(file_path.read_text(encoding="utf-8"))
                    cells = content.get("cells", [])

                    # Extract code cells
                    code_parts = []
                    for cell in cells:
                        if cell.get("cell_type") == "code":
                            source = cell.get("source", [])
                            if isinstance(source, list):
                                code_parts.append("".join(source))
                            else:
                                code_parts.append(source)

                    combined_code = "\n\n".join(code_parts)

                    if self._is_relevant_code(combined_code):
                        extracted = ExtractedCode(
                            file_path=file_path.relative_to(repo_path),
                            language="python",
                            purpose=self._infer_purpose(file_path, combined_code),
                            code=combined_code,
                            dependencies=self._extract_imports(combined_code),
                            can_be_rule=self._can_be_snakemake_rule(combined_code),
                        )
                        notebooks.append(extracted)
                except Exception:
                    continue

        return notebooks

    def _find_config_files(self, repo_path: Path) -> dict[str, str]:
        """Find and read configuration files."""
        configs = {}

        for pattern in self.CONFIG_PATTERNS:
            for file_path in repo_path.rglob(pattern):
                if self._should_skip_path(file_path):
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    rel_path = str(file_path.relative_to(repo_path))
                    configs[rel_path] = content
                except Exception:
                    continue

        return configs

    def _extract_requirements(
        self, repo_path: Path, config_files: dict[str, str]
    ) -> list[str]:
        """Extract Python requirements from config files."""
        requirements = set()

        # From requirements.txt
        if "requirements.txt" in config_files:
            for line in config_files["requirements.txt"].split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    # Remove version specifiers for simplicity
                    pkg = re.split(r"[<>=!]", line)[0].strip()
                    if pkg:
                        requirements.add(pkg)

        # From setup.py
        for path, content in config_files.items():
            if "setup.py" in path:
                # Simple extraction of install_requires
                match = re.search(
                    r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL
                )
                if match:
                    reqs = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
                    for req in reqs:
                        pkg = re.split(r"[<>=!]", req)[0].strip()
                        if pkg:
                            requirements.add(pkg)

        # From pyproject.toml
        for path, content in config_files.items():
            if "pyproject.toml" in path:
                # Simple extraction of dependencies
                match = re.search(
                    r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL
                )
                if match:
                    reqs = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
                    for req in reqs:
                        pkg = re.split(r"[<>=!]", req)[0].strip()
                        if pkg:
                            requirements.add(pkg)

        return list(requirements)

    def _should_skip_path(self, file_path: Path) -> bool:
        """Check if a path should be skipped during parsing."""
        skip_dirs = {
            ".git",
            ".github",
            "__pycache__",
            ".pytest_cache",
            "node_modules",
            ".venv",
            "venv",
            ".tox",
            "build",
            "dist",
            ".eggs",
        }

        for part in file_path.parts:
            if part in skip_dirs or part.startswith("."):
                return True

        return False

    def _is_relevant_code(self, code: str) -> bool:
        """Check if code is relevant to neuroimaging processing."""
        code_lower = code.lower()

        # Check for neuroimaging imports
        for pkg in self.NEUROIMAGING_IMPORTS:
            if pkg in code_lower:
                return True

        # Check for common neuroimaging file patterns
        neuro_patterns = [
            r"\.nii(\.gz)?",
            r"\.mgz",
            r"\.gii",
            r"\.cifti",
            r"BIDS",
            r"fmri",
            r"MRI",
            r"brain",
            r"cortex",
            r"parcellation",
        ]

        for pattern in neuro_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True

        return False

    def _extract_code_info(self, file_path: Path, code: str) -> ExtractedCode:
        """Extract detailed information from a code file."""
        language = self._detect_language(file_path)

        return ExtractedCode(
            file_path=file_path,
            language=language,
            purpose=self._infer_purpose(file_path, code),
            code=code,
            dependencies=self._extract_imports(code) if language == "python" else [],
            can_be_rule=self._can_be_snakemake_rule(code),
        )

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext_map = {
            ".py": "python",
            ".sh": "bash",
            ".bash": "bash",
            ".m": "matlab",
            ".R": "r",
            ".ipynb": "python",
        }
        return ext_map.get(file_path.suffix.lower(), "unknown")

    def _infer_purpose(self, file_path: Path, code: str) -> str:
        """Infer the purpose of a script from its name and content."""
        name = file_path.stem.lower()

        purpose_keywords = {
            "preprocess": "Preprocessing pipeline",
            "preproc": "Preprocessing pipeline",
            "smooth": "Spatial smoothing",
            "register": "Image registration",
            "segment": "Brain segmentation",
            "analysis": "Statistical analysis",
            "glm": "GLM analysis",
            "connectivity": "Connectivity analysis",
            "parcellate": "Brain parcellation",
            "extract": "Feature extraction",
            "qc": "Quality control",
            "denoise": "Denoising",
            "motion": "Motion correction",
        }

        for keyword, purpose in purpose_keywords.items():
            if keyword in name:
                return purpose

        # Check code content
        for keyword, purpose in purpose_keywords.items():
            if keyword in code.lower():
                return purpose

        return "Processing script"

    def _extract_imports(self, code: str) -> list[str]:
        """Extract Python imports from code."""
        imports = set()

        # Match import statements
        import_patterns = [
            r"^import\s+([\w.]+)",
            r"^from\s+([\w.]+)\s+import",
        ]

        for pattern in import_patterns:
            matches = re.findall(pattern, code, re.MULTILINE)
            for match in matches:
                # Get top-level package
                pkg = match.split(".")[0]
                imports.add(pkg)

        return list(imports)

    def _can_be_snakemake_rule(self, code: str) -> bool:
        """Check if code can potentially be converted to a Snakemake rule."""
        # Look for patterns that indicate a self-contained processing step
        indicators = [
            r"if\s+__name__\s*==",  # Has main block
            r"argparse",  # Takes command line arguments
            r"def\s+main\s*\(",  # Has main function
            r"\.nii",  # Works with NIfTI files
            r"save|write|output",  # Produces output
        ]

        score = sum(1 for pattern in indicators if re.search(pattern, code))
        return score >= 2
