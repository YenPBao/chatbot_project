from __future__ import annotations
from dataclasses import dataclass, field
from src.app.ai.shared.configuration import BaseConfiguration

DEFAULT_DOCS_FILE = "src/sample_docs.json"

@dataclass(kw_only=True)
class IndexConfiguration(BaseConfiguration):
    docs_file: str = field(
        default=DEFAULT_DOCS_FILE,
        metadata={
            "description": "Path to a JSON file containing default documents to index."
        },
    )
