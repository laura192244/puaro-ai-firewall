"""Coarse, keyword-based topic classification.

Not NLP/ML — just enough structure to measure whether an account is
systematically sweeping across many unrelated subject areas, which is a
distillation-bot behavior legitimate users rarely exhibit.
"""
from __future__ import annotations

import re

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "coding": ["code", "function", "python", "javascript", "bug", "api", "compile", "algorithm", "debug"],
    "science": ["physics", "chemistry", "biology", "experiment", "hypothesis", "molecule", "quantum"],
    "health": ["symptom", "doctor", "medicine", "diagnosis", "treatment", "disease", "diet", "nutrition"],
    "finance": ["invest", "stock", "budget", "tax", "loan", "interest rate", "portfolio", "currency"],
    "cooking": ["recipe", "bake", "ingredient", "oven", "cook", "grow basil", "kitchen"],
    "legal": ["contract", "lawsuit", "statute", "liability", "regulation", "compliance", "patent"],
    "geography": ["country", "capital", "continent", "population", "border", "climate zone"],
    "history": ["century", "war", "empire", "revolution", "ancient", "historical"],
    "sports": ["team", "match", "score", "tournament", "athlete", "league"],
    "travel": ["flight", "itinerary", "passport", "hotel", "visa", "destination"],
}

_WORD_RE = re.compile(r"[a-z]+(?:\s[a-z]+)?")


def classify(text: str) -> list[str]:
    lowered = text.lower()
    hits = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            hits.append(topic)
    return hits or ["other"]


def all_topics() -> list[str]:
    return list(TOPIC_KEYWORDS.keys()) + ["other"]
