"""Structured relation extraction and validation for M3 clips."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from json_repair import repair_json
from pydantic import BaseModel, ConfigDict, Field

PERSON_PATTERN = re.compile(r"^character_\d+$")
PREDICATE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
NONPERSON_TYPES = {"object", "place", "organization", "concept"}


class GeneratedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    type: Literal["person", "object", "place", "organization", "concept"]


class GeneratedRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clip_id: int = Field(ge=0)
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object: str = Field(min_length=1)
    target: str | None = None
    target_predicate: str | None = None
    evidence: list[str] = Field(min_length=1)
    text: str | None = None


class GeneratedClipGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[GeneratedEntity] = Field(default_factory=list)
    relations: list[GeneratedRelation] = Field(default_factory=list)


@dataclass(frozen=True)
class ValidatedRelation:
    clip_id: int
    subject: str
    predicate: str
    object: str
    target: str | None
    target_predicate: str | None
    evidence: tuple[str, ...]
    text: str


def normalize_nonperson_id(raw_id: str, entity_type: str) -> str:
    if entity_type not in NONPERSON_TYPES:
        raise ValueError(f"Unsupported non-person entity type: {entity_type}")
    value = raw_id.strip().lower()
    prefix = f"{entity_type}_"
    value = value.removeprefix(prefix)
    slug = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    if not slug or len(slug) > 80:
        raise ValueError(f"Invalid {entity_type} ID: {raw_id!r}")
    return f"{entity_type}_{slug}"


class M3RelationBuilder:
    def __init__(
        self,
        llm_client: Any | None = None,
        model_name: str = "gemini-3.8-flash-302",
        **client_kwargs: Any,
    ):
        if llm_client is None:
            from ...llm import LLMClient

            llm_client = LLMClient(model_name=model_name, **client_kwargs)
        self.llm_client = llm_client

    def build_clip(
        self,
        clip_id: int,
        memory_payloads: list[dict[str, Any]],
        known_people: set[str],
    ) -> tuple[dict[str, str], list[ValidatedRelation]]:
        if not memory_payloads:
            return {}, []
        evidence_uids = {item["uid"] for item in memory_payloads}
        prompt = self._prompt(clip_id, memory_payloads, known_people)
        raw = self.llm_client.generate_answer(prompt, temperature=0.0, json_format=True)
        if raw.startswith("Generation failed:"):
            raise RuntimeError("302.AI relation generation failed")
        parsed = GeneratedClipGraph.model_validate(json.loads(repair_json(raw)))

        normalized_entities: dict[str, str] = {
            person: "person" for person in known_people
        }
        aliases: dict[str, str] = {person: person for person in known_people}
        for entity in parsed.entities:
            if entity.type == "person":
                if entity.id not in known_people:
                    raise ValueError(
                        f"Generated relation contains unknown person: {entity.id}"
                    )
                aliases[entity.id] = entity.id
                continue
            normalized = normalize_nonperson_id(entity.id, entity.type)
            aliases[entity.id] = normalized
            normalized_entities[normalized] = entity.type

        validated: list[ValidatedRelation] = []
        for relation in parsed.relations:
            if relation.clip_id != clip_id:
                raise ValueError(
                    f"Generated relation references clip {relation.clip_id}, expected {clip_id}"
                )
            if not PREDICATE_PATTERN.fullmatch(relation.predicate):
                raise ValueError(f"Malformed predicate: {relation.predicate}")
            if relation.target_predicate and not PREDICATE_PATTERN.fullmatch(
                relation.target_predicate
            ):
                raise ValueError(
                    f"Malformed target predicate: {relation.target_predicate}"
                )
            participants = [relation.subject, relation.object]
            if relation.target:
                participants.append(relation.target)
            missing = [item for item in participants if item not in aliases]
            if missing:
                unknown_people = [
                    item for item in missing if PERSON_PATTERN.fullmatch(item)
                ]
                if unknown_people:
                    raise ValueError(
                        f"Generated relation contains unknown people: {unknown_people}"
                    )
                raise ValueError(
                    f"Generated relation references undeclared entities: {missing}"
                )
            subject, obj = aliases[relation.subject], aliases[relation.object]
            target = aliases[relation.target] if relation.target else None
            if subject == obj or (target is not None and target in {subject, obj}):
                raise ValueError("Self-relations are not allowed")
            if len(set(relation.evidence)) != len(relation.evidence):
                raise ValueError("Relation evidence UIDs must be unique")
            nonexistent = set(relation.evidence) - evidence_uids
            if nonexistent:
                raise ValueError(
                    f"Relation references nonexistent evidence: {sorted(nonexistent)}"
                )
            text = (relation.text or f"{subject} {relation.predicate} {obj}").strip()
            validated.append(
                ValidatedRelation(
                    clip_id=clip_id,
                    subject=subject,
                    predicate=relation.predicate,
                    object=obj,
                    target=target,
                    target_predicate=relation.target_predicate,
                    evidence=tuple(relation.evidence),
                    text=text,
                )
            )
        return normalized_entities, validated

    @staticmethod
    def _prompt(
        clip_id: int, memories: list[dict[str, Any]], known_people: set[str]
    ) -> str:
        payload = {
            "clip_id": clip_id,
            "known_people": sorted(known_people),
            "evidence": memories,
        }
        return (
            "Extract only evidence-supported entity relations from this single video clip. "
            "Preserve every person ID exactly and never invent or merge people. Declare each non-person "
            "entity with type object, place, organization, or concept. Predicates must be lowercase snake_case. "
            "Every relation must include clip_id and one or more exact evidence UIDs from the input. "
            "Return JSON with keys entities and relations; relation keys are clip_id, subject, predicate, object, "
            "optional target, optional target_predicate, evidence, and optional text.\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )
