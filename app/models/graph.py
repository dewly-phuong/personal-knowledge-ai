from typing import Literal
from pydantic import BaseModel, Field

EntityType = Literal["PERSON", "ORGANIZATION", "SERVICE", "PIPELINE", "CONCEPT", "ARTIFACT", "DATABASE"]

class Entity(BaseModel):
    name: str = Field(description="Canonical capitalized name of the entity, e.g., 'Auth Service'")
    type: EntityType
    description: str = Field(description="A concise one-sentence description grounded in the document.")

class Relation(BaseModel):
    source: str = Field(description="Name of the source entity")
    predicate: str = Field(description="Short verb phrase (lowercase), e.g., 'depends on', 'owns'")
    target: str = Field(description="Name of the target entity")

class ExtractedGraph(BaseModel):
    entities: list[Entity]
    relations: list[Relation]

class Cluster(BaseModel):
    canonical: str = Field(description="The most complete, unambiguous form of the entity name")
    aliases: list[str] = Field(description="All surface form names referring to this entity")

class ResolvedClusters(BaseModel):
    clusters: list[Cluster]

class TimeRange(BaseModel):
    start: str = Field(description="YYYY or 'unknown'")
    end: str = Field(description="YYYY or 'ongoing'")

class EntityProfile(BaseModel):
    summary: str = Field(description="2-3 paragraphs profiling the entity")
    key_facts: list[str] = Field(description="3-5 atomic facts, traceable to sources")
    time_range: TimeRange
