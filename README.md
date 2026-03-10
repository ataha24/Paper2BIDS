# Paper2BIDS

Transform neuroimaging papers and their code into reproducible [snakebids](https://github.com/khanlab/snakebids) applications.

## Overview

Paper2BIDS bridges the gap between academic publications and reproducible neuroimaging pipelines. It takes a neuroimaging paper (PDF) and/or its associated code repository and generates a complete snakebids application that others can use to reproduce the analysis.

Inspired by [Paper2Agent](https://github.com/jmiao24/Paper2Agent), but specifically designed for the neuroimaging community using BIDS standards.

## Features

- **Paper Parsing**: Extract methodology from PDF papers
- **Code Analysis**: Understand processing pipelines from repositories
- **LLM-Powered Understanding**: Uses Claude to intelligently extract and merge pipeline information
- **Snakebids Generation**: Produces complete, runnable BIDS apps
- **BIDS Compliance**: Generated apps follow BIDS App guidelines

## Installation

```bash
pip install paper2bids
```

Or install from source:

```bash
git clone https://github.com/yourorg/paper2bids
cd paper2bids
pip install -e ".[dev]"
```

## Requirements

- Python 3.10+
- Anthropic API key (for LLM analysis)

## Quick Start

### From a paper and repository

```bash
export ANTHROPIC_API_KEY=your-api-key

# Convert paper + code to snakebids app
paper2bids convert paper.pdf --repo-url https://github.com/user/analysis-code -o ./output
```

### From repository only

```bash
paper2bids from-repo https://github.com/nilearn/nilearn -o ./output
```

### From paper only

```bash
paper2bids from-paper methodology_paper.pdf -o ./output
```

## Python API

```python
from pathlib import Path
from paper2bids import Paper2BIDS

converter = Paper2BIDS(api_key="your-api-key")

# From paper and repository
app_path = converter.from_paper_and_repo(
    paper_path=Path("paper.pdf"),
    repo_url="https://github.com/user/repo",
    output_dir=Path("./output"),
)

# From repository only
app_path = converter.from_repository(
    repo_url="https://github.com/user/repo",
    output_dir=Path("./output"),
)

# From paper only
app_path = converter.from_paper(
    paper_path=Path("paper.pdf"),
    output_dir=Path("./output"),
)
```

## How It Works

1. **Parse Paper**: Extract text from PDF, identify methods section, find software mentions
2. **Parse Repository**: Clone repo, find relevant scripts/notebooks, extract code patterns
3. **Analyze Methodology**: Use Claude to understand the processing pipeline from paper text
4. **Analyze Code**: Use Claude to understand code structure and convert to Snakemake rules
5. **Merge Understanding**: Combine paper methodology with code implementation
6. **Generate Snakebids App**: Output a complete, runnable snakebids application

## Generated App Structure

```
my_pipeline/
├── run.py              # BIDS App entry point
├── pyproject.toml      # Python package config
├── README.md           # Documentation
├── config/
│   └── snakebids.yml   # Snakebids configuration
└── workflow/
    ├── Snakefile       # Main workflow
    ├── rules/          # Additional rules
    └── scripts/        # Helper scripts
```

## Usage of Generated Apps

```bash
cd my_pipeline
pip install -e .

# Run as BIDS App
./run.py /path/to/bids /path/to/output participant

# Or with Snakemake directly
snakemake --cores all --config bids_dir=/path/to/bids
```

## Supported Software Detection

Paper2BIDS recognizes mentions of common neuroimaging software:

- FSL
- FreeSurfer
- SPM
- AFNI
- ANTs
- MRtrix3
- Nipype
- fMRIPrep
- Nilearn
- And more...

## Contributing

Contributions are welcome! Please see our contributing guidelines.

```bash
# Development setup
pip install -e ".[dev]"

# Run tests
pytest

# Format code
ruff format .
ruff check . --fix
```

## License

MIT License - see LICENSE file.

## Acknowledgments

- [snakebids](https://github.com/khanlab/snakebids) - The framework we generate apps for
- [Paper2Agent](https://github.com/jmiao24/Paper2Agent) - Inspiration for the concept
- [BIDS](https://bids.neuroimaging.io) - Brain Imaging Data Structure
- [Anthropic Claude](https://anthropic.com) - LLM for understanding papers and code

## Citation

If you use Paper2BIDS in your research, please cite:

```bibtex
@software{paper2bids,
  title = {Paper2BIDS: Transform Neuroimaging Papers into Reproducible BIDS Applications},
  year = {2026},
  url = {https://github.com/ataha24/paper2bids}
}
```
