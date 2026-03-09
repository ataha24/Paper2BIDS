"""Analyzer for extracting methodology from papers using LLM."""

from anthropic import Anthropic

from paper2bids.models import (
    BIDSInput,
    PaperContent,
    PipelineSpecification,
    ProcessingStep,
)


class MethodologyAnalyzer:
    """Analyze paper content to extract pipeline methodology using Claude."""

    SYSTEM_PROMPT = """You are an expert neuroimaging researcher who specializes in
understanding and extracting processing pipelines from academic papers. Your task is
to analyze paper content and extract detailed information about the neuroimaging
processing pipeline described.

Focus on:
1. Input data requirements (what BIDS data types are needed)
2. Processing steps in order (preprocessing, registration, analysis, etc.)
3. Software and tools used (FSL, FreeSurfer, ANTs, etc.)
4. Parameters and settings mentioned
5. Output products of the pipeline

Be precise and technical. Extract concrete, actionable information that can be used
to recreate the pipeline."""

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the methodology analyzer.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
        """
        self.client = Anthropic(api_key=api_key)

    def analyze(self, paper: PaperContent) -> PipelineSpecification:
        """Analyze paper content and extract pipeline specification.

        Args:
            paper: Parsed paper content.

        Returns:
            PipelineSpecification with extracted methodology.
        """
        # First, extract high-level information
        overview = self._extract_overview(paper)

        # Then, extract detailed processing steps
        steps = self._extract_processing_steps(paper)

        # Extract BIDS input requirements
        inputs = self._extract_bids_inputs(paper)

        # Extract software dependencies
        software = self._extract_software(paper)

        return PipelineSpecification(
            title=paper.title,
            description=overview.get("description", ""),
            inputs=inputs,
            steps=steps,
            outputs=overview.get("outputs", []),
            software_dependencies=software,
            python_dependencies=self._infer_python_deps(software),
        )

    def _extract_overview(self, paper: PaperContent) -> dict:
        """Extract high-level overview of the pipeline."""
        prompt = f"""Analyze this neuroimaging paper and extract:
1. A brief description of what the pipeline does (1-2 sentences)
2. The main outputs/products of the pipeline
3. The analysis level (participant-level, group-level, or both)

Paper Title: {paper.title}

Abstract:
{paper.abstract}

Methods Section:
{paper.methods_section[:4000] if paper.methods_section else "Not available"}

Respond in this exact format:
DESCRIPTION: <description>
OUTPUTS: <comma-separated list of outputs>
ANALYSIS_LEVEL: <participant|group|both>"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        result = {"description": "", "outputs": [], "analysis_level": "participant"}

        for line in text.strip().split("\n"):
            if line.startswith("DESCRIPTION:"):
                result["description"] = line.replace("DESCRIPTION:", "").strip()
            elif line.startswith("OUTPUTS:"):
                outputs = line.replace("OUTPUTS:", "").strip()
                result["outputs"] = [o.strip() for o in outputs.split(",")]
            elif line.startswith("ANALYSIS_LEVEL:"):
                result["analysis_level"] = line.replace("ANALYSIS_LEVEL:", "").strip()

        return result

    def _extract_processing_steps(self, paper: PaperContent) -> list[ProcessingStep]:
        """Extract detailed processing steps from the methods section."""
        if not paper.methods_section:
            return []

        prompt = f"""Analyze this methods section and extract each processing step in order.

Methods Section:
{paper.methods_section[:6000]}

For each processing step, provide:
- NAME: Short name for the step (e.g., "motion_correction", "spatial_smoothing")
- DESCRIPTION: What this step does
- INPUTS: What data/files this step takes as input
- OUTPUTS: What data/files this step produces
- SOFTWARE: What software/tool is used (if mentioned)
- COMMAND: Shell command if mentioned (or "unknown")
- PARAMETERS: Any parameters mentioned (as key=value pairs)

Format each step as:
---STEP---
NAME: <name>
DESCRIPTION: <description>
INPUTS: <comma-separated inputs>
OUTPUTS: <comma-separated outputs>
SOFTWARE: <software or "unknown">
COMMAND: <command or "unknown">
PARAMETERS: <param1=value1, param2=value2>
---END---

Extract ALL processing steps mentioned, in order."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        steps = []

        # Parse steps from response
        step_blocks = text.split("---STEP---")[1:]  # Skip first empty part

        for block in step_blocks:
            if "---END---" in block:
                block = block.split("---END---")[0]

            step_data = {}
            for line in block.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    step_data[key.strip().lower()] = value.strip()

            if "name" in step_data:
                # Parse parameters
                params = {}
                if "parameters" in step_data and step_data["parameters"] != "unknown":
                    for param in step_data["parameters"].split(","):
                        if "=" in param:
                            k, v = param.split("=", 1)
                            params[k.strip()] = v.strip()

                step = ProcessingStep(
                    name=step_data.get("name", "unknown_step"),
                    description=step_data.get("description", ""),
                    inputs=self._parse_list(step_data.get("inputs", "")),
                    outputs=self._parse_list(step_data.get("outputs", "")),
                    command=step_data.get("command")
                    if step_data.get("command") != "unknown"
                    else None,
                    software=step_data.get("software")
                    if step_data.get("software") != "unknown"
                    else None,
                    parameters=params,
                )
                steps.append(step)

        return steps

    def _extract_bids_inputs(self, paper: PaperContent) -> list[BIDSInput]:
        """Extract BIDS input requirements from the paper."""
        prompt = f"""Analyze this paper and determine what BIDS input data is required.

Title: {paper.title}
Abstract: {paper.abstract}
Methods: {paper.methods_section[:3000] if paper.methods_section else "Not available"}

For each required input type, specify:
- NAME: Input name (e.g., "bold", "t1w", "dwi", "flair")
- SUFFIX: BIDS suffix (e.g., "bold", "T1w", "dwi")
- DATATYPE: BIDS datatype (e.g., "func", "anat", "dwi")
- EXTENSION: File extension (usually ".nii.gz")
- WILDCARDS: Which BIDS entities vary (e.g., "subject,session,run")

Format:
---INPUT---
NAME: <name>
SUFFIX: <suffix>
DATATYPE: <datatype>
EXTENSION: <extension>
WILDCARDS: <comma-separated wildcards>
---END---"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        inputs = []

        input_blocks = text.split("---INPUT---")[1:]

        for block in input_blocks:
            if "---END---" in block:
                block = block.split("---END---")[0]

            input_data = {}
            for line in block.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    input_data[key.strip().lower()] = value.strip()

            if "name" in input_data:
                bids_input = BIDSInput(
                    name=input_data.get("name", "input"),
                    filters={
                        "suffix": input_data.get("suffix", "bold"),
                        "extension": input_data.get("extension", ".nii.gz"),
                        "datatype": input_data.get("datatype", "func"),
                    },
                    wildcards=self._parse_list(input_data.get("wildcards", "subject")),
                )
                inputs.append(bids_input)

        # Default to BOLD input if nothing found
        if not inputs:
            inputs.append(
                BIDSInput(
                    name="bold",
                    filters={
                        "suffix": "bold",
                        "extension": ".nii.gz",
                        "datatype": "func",
                    },
                    wildcards=["subject", "session", "task", "run"],
                )
            )

        return inputs

    def _extract_software(self, paper: PaperContent) -> list[str]:
        """Extract software dependencies mentioned in the paper."""
        prompt = f"""List all neuroimaging software and tools mentioned in this paper.

Title: {paper.title}
Methods: {paper.methods_section[:4000] if paper.methods_section else paper.full_text[:4000]}

Return ONLY a comma-separated list of software names (e.g., "FSL, FreeSurfer, ANTs, SPM").
If none are mentioned, return "unknown"."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.lower() == "unknown":
            return []

        return [s.strip() for s in text.split(",") if s.strip()]

    def _parse_list(self, text: str) -> list[str]:
        """Parse a comma-separated list from text."""
        if not text or text.lower() in ("unknown", "none", "n/a"):
            return []
        return [item.strip() for item in text.split(",") if item.strip()]

    def _infer_python_deps(self, software: list[str]) -> list[str]:
        """Infer Python dependencies from software list."""
        deps = ["snakebids", "pybids", "nibabel"]

        software_to_python = {
            "fsl": ["nipype"],
            "freesurfer": ["nipype"],
            "ants": ["antspyx"],
            "spm": ["nipype"],
            "nilearn": ["nilearn"],
            "mrtrix": ["nipype"],
            "fmriprep": ["fmriprep"],
            "conn": ["nilearn"],
        }

        for sw in software:
            sw_lower = sw.lower()
            for key, python_deps in software_to_python.items():
                if key in sw_lower:
                    deps.extend(python_deps)

        return list(set(deps))
