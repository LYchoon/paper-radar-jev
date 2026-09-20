from dataclasses import dataclass, field


@dataclass
class Paper:
    id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    published: str
    updated: str | None
    url: str


@dataclass
class EvaluatedPaper(Paper):
    relevant: bool = False
    relevance_score: float = 0.0
    dimension_scores: dict[str, float] = field(default_factory=dict)
