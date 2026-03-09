"""Parsers for extracting information from papers and code repositories."""

from paper2bids.parsers.paper import PaperParser
from paper2bids.parsers.repository import RepositoryParser

__all__ = ["PaperParser", "RepositoryParser"]
