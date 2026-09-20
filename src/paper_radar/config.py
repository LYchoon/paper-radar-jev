"""Strict configuration validation and stable path resolution."""
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Profile(Schema):
    name: Text
    description: str = ""


class Research(Schema):
    summary: Text
    interests: list[Text] = Field(default_factory=list)
    related_topics: list[Text] = Field(default_factory=list)
    negative_topics: list[Text] = Field(default_factory=list)
    evaluation_guidance: list[Text] = Field(default_factory=list)


class Arxiv(Schema):
    enabled: bool = True
    categories: list[Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9.-]*$")]] = Field(min_length=1)
    max_results: int = Field(default=300, gt=0)
    sort_by: Literal["submitted_date", "last_updated_date", "relevance"] = "submitted_date"
    sort_order: Literal["descending", "ascending"] = "descending"


class Sources(Schema):
    arxiv: Arxiv


class Dimensions(Schema):
    enabled: bool = False
    questions: dict[Text, Text] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_names(self):
        if "relevant" in self.questions:
            raise ValueError("dimensions.questions: 'relevant' is reserved")
        if self.enabled and not self.questions:
            raise ValueError("enabled dimensions require questions")
        return self


class Evaluation(Schema):
    relevance_threshold: Probability = 0.5
    high_priority_threshold: Probability = 0.8
    dimensions: Dimensions = Field(default_factory=Dimensions)

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.high_priority_threshold < self.relevance_threshold:
            raise ValueError("high_priority_threshold must be >= relevance_threshold")
        return self


class Storage(Schema):
    seen_file: Text = "data/seen.json"
    database_file: Text = "data/papers.jsonl"
    daily_output_dir: Text = "daily"


class Output(Schema):
    markdown: bool = True
    json: bool = True
    include_irrelevant: bool = False
    max_papers_in_report: int = Field(default=50, gt=0)
    sort_by: Literal["relevance_score"] = "relevance_score"
    sort_order: Literal["descending", "ascending"] = "descending"

    @model_validator(mode="after")
    def validate_formats(self):
        if not (self.markdown or self.json):
            raise ValueError("at least one output format must be enabled")
        return self


class Config(Schema):
    profile: Profile
    research: Research
    sources: Sources
    evaluation: Evaluation = Field(default_factory=Evaluation)
    storage: Storage = Field(default_factory=Storage)
    output: Output = Field(default_factory=Output)


def load_config(path: str | Path) -> Config:
    # Accept PowerShell's UTF-8 BOM as well as ordinary UTF-8.
    with Path(path).open(encoding="utf-8-sig") as stream:
        return Config.model_validate(json.load(stream))


def storage_paths(config: Config, config_path: Path) -> tuple[Path, Path, Path]:
    parent = config_path.resolve().parent
    base = parent.parent if parent.name == "config" else parent
    paths = tuple((base / value).resolve() for value in (
        config.storage.seen_file, config.storage.database_file,
        config.storage.daily_output_dir,
    ))
    seen, database, daily = paths
    if seen == database or any(p == daily or p.is_relative_to(daily) for p in (seen, database)):
        raise ValueError("seen/database must be distinct files outside the daily directory")
    return seen, database, daily
