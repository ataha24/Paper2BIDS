"""Parser for extracting information from academic papers."""

import re
from pathlib import Path

import fitz  # PyMuPDF - better for complex layouts like Nature journals

from paper2bids.models import PaperContent


class PaperParser:
    """Parse academic papers (PDF or text) to extract methodology information."""

    # Common neuroimaging software patterns
    SOFTWARE_PATTERNS = [
        r"\b(FSL|FMRIB Software Library)\b",
        r"\b(FreeSurfer)\b",
        r"\b(SPM|Statistical Parametric Mapping)\b",
        r"\b(AFNI)\b",
        r"\b(ANTs|Advanced Normalization Tools)\b",
        r"\b(MRtrix3?)\b",
        r"\b(Nipype)\b",
        r"\b(fMRIPrep)\b",
        r"\b(CONN)\b",
        r"\b(CAT12)\b",
        r"\b(BrainVoyager)\b",
        r"\b(DSI Studio)\b",
        r"\b(Connectome Workbench)\b",
    ]

    # Common processing step patterns
    PROCESSING_PATTERNS = {
        "preprocessing": [
            r"motion correction",
            r"slice.?timing correction",
            r"spatial normalization",
            r"skull.?strip",
            r"brain extraction",
            r"bias.?field correction",
            r"distortion correction",
        ],
        "registration": [
            r"registration",
            r"coregistration",
            r"alignment",
            r"transformation",
            r"normalization to (MNI|template)",
        ],
        "segmentation": [
            r"segmentation",
            r"tissue classification",
            r"parcellation",
            r"(gray|grey|white) matter",
        ],
        "smoothing": [
            r"smooth(ing|ed)?",
            r"gaussian (filter|kernel)",
            r"FWHM",
            r"spatial filter",
        ],
        "statistical_analysis": [
            r"GLM|general linear model",
            r"statistical analysis",
            r"first.?level analysis",
            r"second.?level analysis",
            r"group analysis",
        ],
    }

    def __init__(self) -> None:
        """Initialize the paper parser."""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficiency."""
        self._software_re = [
            re.compile(p, re.IGNORECASE) for p in self.SOFTWARE_PATTERNS
        ]
        self._processing_re = {
            category: [re.compile(p, re.IGNORECASE) for p in patterns]
            for category, patterns in self.PROCESSING_PATTERNS.items()
        }

    def parse_pdf(self, pdf_path: Path) -> PaperContent:
        """Parse a PDF file and extract content.

        Uses PyMuPDF (fitz) for better handling of complex multi-column
        layouts common in journals like Nature, Science, etc.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            PaperContent with extracted information.
        """
        doc = fitz.open(pdf_path)

        full_text = ""
        for page in doc:
            # Use "text" extraction with sorting for proper reading order
            # This handles multi-column layouts much better than pypdf
            text = page.get_text("text", sort=True)
            if text:
                full_text += text + "\n"

        doc.close()
        return self._parse_text(full_text)

    def parse_text(self, text: str) -> PaperContent:
        """Parse raw text content from a paper.

        Args:
            text: The paper text content.

        Returns:
            PaperContent with extracted information.
        """
        return self._parse_text(text)

    def _parse_text(self, text: str) -> PaperContent:
        """Internal method to parse text content.

        Args:
            text: The paper text content.

        Returns:
            PaperContent with extracted information.
        """
        title = self._extract_title(text)
        abstract = self._extract_abstract(text)
        methods = self._extract_methods(text)

        return PaperContent(
            title=title,
            abstract=abstract,
            methods_section=methods,
            full_text=text,
            figures=self._extract_figure_captions(text),
            references=self._extract_references(text),
        )

    def _extract_title(self, text: str) -> str:
        """Extract the paper title from text."""
        lines = text.strip().split("\n")
        # Title is usually in the first few non-empty lines
        for line in lines[:10]:
            line = line.strip()
            if len(line) > 10 and len(line) < 200:
                # Skip common header text
                if not any(
                    skip in line.lower()
                    for skip in ["abstract", "introduction", "doi:", "http"]
                ):
                    return line
        return "Unknown Title"

    def _extract_abstract(self, text: str) -> str:
        """Extract the abstract section."""
        # Look for explicit "Abstract" section
        abstract_match = re.search(
            r"(?:^|\n)\s*Abstract\s*\n(.*?)(?=\n\s*(?:Introduction|Keywords|1\.|Background))",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if abstract_match:
            return abstract_match.group(1).strip()
        return ""

    def _extract_methods(self, text: str) -> str:
        """Extract the methods/materials section."""
        # Look for Methods section with various common headers
        methods_patterns = [
            r"(?:^|\n)\s*(?:Materials?\s+and\s+)?Methods?\s*\n(.*?)(?=\n\s*(?:Results?|Discussion|Acknowledgment))",
            r"(?:^|\n)\s*(?:2\.?\s*)?Methods?\s*\n(.*?)(?=\n\s*(?:3\.?\s*)?Results?)",
            r"(?:^|\n)\s*Experimental\s+(?:Design|Procedures?)\s*\n(.*?)(?=\n\s*Results?)",
        ]

        for pattern in methods_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_figure_captions(self, text: str) -> list[str]:
        """Extract figure captions from the text."""
        captions = []
        pattern = r"(?:Figure|Fig\.?)\s*(\d+)[.:]?\s*([^\n]+(?:\n(?![A-Z])[^\n]+)*)"
        matches = re.finditer(pattern, text, re.IGNORECASE)

        for match in matches:
            caption = f"Figure {match.group(1)}: {match.group(2).strip()}"
            captions.append(caption)

        return captions

    def _extract_references(self, text: str) -> list[str]:
        """Extract references section."""
        refs_match = re.search(
            r"(?:^|\n)\s*References?\s*\n(.*?)$",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if refs_match:
            refs_text = refs_match.group(1)
            # Split by numbered references or newlines
            refs = re.split(r"\n\s*\[\d+\]|\n\s*\d+\.\s+", refs_text)
            return [r.strip() for r in refs if r.strip() and len(r.strip()) > 20]
        return []

    def extract_software(self, text: str) -> list[str]:
        """Extract mentioned neuroimaging software from text.

        Args:
            text: Paper text content.

        Returns:
            List of identified software packages.
        """
        found_software = set()
        for pattern in self._software_re:
            matches = pattern.findall(text)
            found_software.update(matches)
        return list(found_software)

    def extract_processing_steps(self, text: str) -> dict[str, list[str]]:
        """Extract mentioned processing steps from text.

        Args:
            text: Paper text content.

        Returns:
            Dictionary mapping processing categories to found steps.
        """
        found_steps: dict[str, list[str]] = {}

        for category, patterns in self._processing_re.items():
            matches = []
            for pattern in patterns:
                found = pattern.findall(text)
                matches.extend(found)
            if matches:
                found_steps[category] = list(set(matches))

        return found_steps
