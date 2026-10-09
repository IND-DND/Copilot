"""Shared evidence prompt and checks for the Ollama and ZeroGPU runners."""

import json
import logging
import re

from .prompts import SYSTEM_PROMPT


def reject(reason):
    # Record a check name only, never the question, generated text, or evidence.
    logging.getLogger(__name__).warning("Model response rejected: %s", reason)
    return None, "rejected"


def model_messages(question, language, sources):
    language_instruction = (
        "\nइस उत्तर के JSON summary में केवल हिंदी (देवनागरी लिपि) में लिखें, भले ही सवाल अंग्रेज़ी में हो। "
        "दो छोटे वाक्यों में दिए गए स्रोतों का संदर्भ समझाएँ। citations में मूल evidence IDs ही रखें।"
        if language == "hi" else "\nWrite this response's JSON summary in English."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT + language_instruction},
        {"role": "user", "content": json.dumps({
            "question": question,
            "language": "Hindi" if language == "hi" else "English",
            "evidence": [{"id": s.id, "reference": s.reference, "text": s.text, "note": s.note} for s in sources],
        }, ensure_ascii=False)},
    ]


def checked_summary(content, language, sources):
    """Check structure and references; this is not a factual correctness proof."""
    if isinstance(content, str):
        # Some instruction models wrap otherwise valid JSON in one code fence.
        # Accept only that complete envelope, never text surrounding an object.
        wrapped = re.fullmatch(r"\s*```(?:json)?\s*(\{[\s\S]*\})\s*```\s*", content)
        if wrapped:
            content = wrapped[1]
    try:
        data = json.loads(content)
        summary, cited = data.get("summary"), data.get("citations")
    except (ValueError, TypeError, AttributeError):
        reason = "json_format"
        if isinstance(content, str):
            if content.lstrip().startswith("```"):
                reason = "json_fence_incomplete"
            elif not content.lstrip().startswith("{"):
                reason = "json_preface"
            elif not content.rstrip().endswith("}"):
                reason = "json_incomplete"
        return reject(reason)
    allowed = {s.id for s in sources}
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 2500 or not isinstance(cited, list) or not cited or not all(isinstance(c, str) and c in allowed for c in cited):
        return reject("summary_or_citation_structure")
    valid_refs = {match for s in sources for match in re.findall(r"\b\d{1,3}:\d{1,3}\b", s.reference)}
    if re.search(r'https?://|www\.', summary):
        return reject("new_link")
    if re.search(r'[\u0600-\u06ff]', summary):
        return reject("generated_arabic")
    if re.search(r'["“”]', summary):
        return reject("quoted_text")
    if any(ref not in valid_refs for ref in re.findall(r"\b\d{1,3}:\d{1,3}\b", summary)):
        return reject("unknown_quran_reference")
    hadith_refs = re.findall(r"\b(bukhari|muslim)\s*[:#]?\s*(\d+[a-z]?)\b", summary.lower())
    if any(f"{collection}-{number}" not in allowed for collection, number in hadith_refs):
        return reject("unknown_hadith_reference")
    if language == "hi" and not re.search(r"[\u0900-\u097f]", summary):
        return reject("hindi_language")
    return summary.strip(), "used"
