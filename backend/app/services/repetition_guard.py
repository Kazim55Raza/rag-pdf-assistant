import re
from difflib import SequenceMatcher
from typing import Any, Dict, List


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip().lower()


def deduplicate_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove exact and near-duplicate chunks from the same page before sending them to the LLM."""
    unique_chunks: List[Dict[str, Any]] = []
    seen_signatures: List[tuple[int, str]] = []

    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        if not text:
            continue

        normalized = _normalized_text(text)
        page_number = int(chunk.get("page_number") or 0)

        duplicate = False
        for seen_page, seen_text in seen_signatures:
            if seen_page != page_number:
                continue

            if normalized == seen_text or normalized in seen_text or seen_text in normalized:
                duplicate = True
                break

            similarity = SequenceMatcher(None, seen_text, normalized).ratio()
            if similarity >= 0.9:
                duplicate = True
                break

        if duplicate:
            continue

        unique_chunks.append(chunk)
        seen_signatures.append((page_number, normalized))

    return unique_chunks


def collapse_repeated_phrases(text: str) -> str:
    """Remove repeated sentences or repeated word phrases from generated text."""
    if not text:
        return text

    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]
    unique_sentences: List[str] = []
    seen_sentences = set()

    for sentence in sentences:
        key = _normalized_text(sentence)
        if key not in seen_sentences:
            unique_sentences.append(sentence)
            seen_sentences.add(key)

    collapsed = " ".join(unique_sentences)
    if not collapsed:
        return normalized

    pattern = re.compile(r"(?i)\b((?:\w+\s+){0,4}\w+)\b(?:\s+\1)+")
    while True:
        updated = pattern.sub(r"\1", collapsed)
        if updated == collapsed:
            break
        collapsed = updated

    return collapsed.strip()
