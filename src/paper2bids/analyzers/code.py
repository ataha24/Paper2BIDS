"""Analyzer for understanding code structure and generating Snakemake rules."""

from anthropic import Anthropic

from paper2bids.models import ExtractedCode, ProcessingStep, RepositoryContent


class CodeAnalyzer:
    """Analyze repository code to understand processing logic and generate rules."""

    SYSTEM_PROMPT = """You are an expert in neuroimaging pipelines and Snakemake
workflow development. Your task is to analyze code from neuroimaging repositories
and understand how to convert it into Snakemake rules for a snakebids application.

Focus on:
1. Understanding what each script/function does
2. Identifying inputs and outputs
3. Determining how to parameterize the code
4. Converting processing logic to Snakemake rule format"""

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the code analyzer.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
        """
        self.client = Anthropic(api_key=api_key)

    def analyze_repository(
        self, repo_content: RepositoryContent
    ) -> list[ProcessingStep]:
        """Analyze repository code and extract processing steps.

        Args:
            repo_content: Parsed repository content.

        Returns:
            List of ProcessingSteps derived from the code.
        """
        steps = []

        # Analyze scripts
        for script in repo_content.scripts:
            if script.can_be_rule:
                step = self._analyze_script(script)
                if step:
                    steps.append(step)

        # Analyze notebooks
        for notebook in repo_content.notebooks:
            if notebook.can_be_rule:
                step = self._analyze_script(notebook)
                if step:
                    steps.append(step)

        return steps

    def _analyze_script(self, code: ExtractedCode) -> ProcessingStep | None:
        """Analyze a single script and convert to a ProcessingStep."""
        if len(code.code) > 10000:
            # Truncate very long scripts
            code_text = code.code[:10000] + "\n... (truncated)"
        else:
            code_text = code.code

        prompt = f"""Analyze this {code.language} script and extract information for
converting it to a Snakemake rule.

File: {code.file_path}
Purpose: {code.purpose}

Code:
```{code.language}
{code_text}
```

Extract:
1. NAME: A short snake_case name for this processing step
2. DESCRIPTION: What this code does (1-2 sentences)
3. INPUTS: What input files/data does it expect (comma-separated)
4. OUTPUTS: What output files does it produce (comma-separated)
5. COMMAND: The shell command to run this (if it's a script), or "python {{script}}"
6. PARAMETERS: Any configurable parameters (as param=default_value pairs)

If this code cannot be reasonably converted to a Snakemake rule, respond with
"NOT_CONVERTIBLE" and explain why.

Format:
NAME: <name>
DESCRIPTION: <description>
INPUTS: <inputs>
OUTPUTS: <outputs>
COMMAND: <command>
PARAMETERS: <parameters>"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text

        if "NOT_CONVERTIBLE" in text:
            return None

        # Parse response
        data = {}
        for line in text.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip().lower()] = value.strip()

        if "name" not in data:
            return None

        # Parse parameters
        params = {}
        if "parameters" in data and data["parameters"].lower() not in (
            "none",
            "n/a",
            "",
        ):
            for param in data["parameters"].split(","):
                if "=" in param:
                    k, v = param.split("=", 1)
                    params[k.strip()] = v.strip()

        return ProcessingStep(
            name=data.get("name", "unknown"),
            description=data.get("description", ""),
            inputs=self._parse_list(data.get("inputs", "")),
            outputs=self._parse_list(data.get("outputs", "")),
            command=data.get("command"),
            parameters=params,
        )

    def generate_snakemake_rule(self, step: ProcessingStep, input_name: str) -> str:
        """Generate a Snakemake rule from a ProcessingStep.

        Args:
            step: The processing step to convert.
            input_name: Name of the snakebids input to use.

        Returns:
            Snakemake rule as a string.
        """
        prompt = f"""Generate a Snakemake rule for a snakebids workflow based on this
processing step:

Name: {step.name}
Description: {step.description}
Inputs: {', '.join(step.inputs)}
Outputs: {', '.join(step.outputs)}
Command: {step.command or 'unknown'}
Parameters: {step.parameters}

The rule should:
1. Use snakebids conventions (bids() function for output paths)
2. Use wildcards appropriately
3. Include proper input/output declarations
4. Use params section for any parameters
5. Have a proper shell or run section

Input BidsComponent name: {input_name}

Generate ONLY the Snakemake rule code, no explanations."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text.strip()

    def merge_steps(
        self, paper_steps: list[ProcessingStep], code_steps: list[ProcessingStep]
    ) -> list[ProcessingStep]:
        """Merge processing steps from paper and code analysis.

        Args:
            paper_steps: Steps extracted from paper methodology.
            code_steps: Steps extracted from code analysis.

        Returns:
            Merged list of ProcessingSteps.
        """
        if not code_steps:
            return paper_steps

        if not paper_steps:
            return code_steps

        # Use LLM to intelligently merge
        paper_summary = "\n".join(
            f"- {s.name}: {s.description}" for s in paper_steps
        )
        code_summary = "\n".join(f"- {s.name}: {s.description}" for s in code_steps)

        prompt = f"""I have processing steps extracted from a paper's methods section
and from the associated code repository. Help me merge them into a unified pipeline.

Steps from paper:
{paper_summary}

Steps from code:
{code_summary}

For each step in the merged pipeline, tell me:
1. Which paper step(s) it corresponds to (by index, 0-based)
2. Which code step(s) it corresponds to (by index, 0-based)
3. If it's paper-only, code-only, or matched

Format as:
STEP: <name>
PAPER_IDX: <index or "none">
CODE_IDX: <index or "none">
---"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        merged = []

        # Parse merge instructions
        for block in text.split("---"):
            block = block.strip()
            if not block:
                continue

            data = {}
            for line in block.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    data[key.strip().lower()] = value.strip()

            paper_idx = data.get("paper_idx", "none")
            code_idx = data.get("code_idx", "none")

            # Prefer code step if available (more concrete)
            if code_idx != "none":
                try:
                    idx = int(code_idx)
                    if 0 <= idx < len(code_steps):
                        merged.append(code_steps[idx])
                        continue
                except ValueError:
                    pass

            # Fall back to paper step
            if paper_idx != "none":
                try:
                    idx = int(paper_idx)
                    if 0 <= idx < len(paper_steps):
                        merged.append(paper_steps[idx])
                except ValueError:
                    pass

        # If merging failed, just concatenate
        if not merged:
            return paper_steps + code_steps

        return merged

    def _parse_list(self, text: str) -> list[str]:
        """Parse a comma-separated list from text."""
        if not text or text.lower() in ("unknown", "none", "n/a"):
            return []
        return [item.strip() for item in text.split(",") if item.strip()]
