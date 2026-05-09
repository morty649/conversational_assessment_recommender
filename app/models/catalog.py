from dataclasses import dataclass
from typing import List

@dataclass
class CatalogItem:
    entity_id: str
    name: str
    link: str
    description: str
    job_levels: List[str]
    languages: List[str]
    duration: str
    remote: str
    adaptive: str
    keys: List[str]

    def searchable_text(self) -> str:
        return f"""
        Name: {self.name}
        Description: {self.description}
        Job Levels: {", ".join(self.job_levels)}
        Languages: {", ".join(self.languages)}
        Duration: {self.duration}
        Remote: {self.remote}
        Adaptive: {self.adaptive}
        Categories: {", ".join(self.keys)}
        """