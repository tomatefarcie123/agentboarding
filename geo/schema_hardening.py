"""Schema.org JSON-LD hardening.

`harden_jsonld()` post-processes the metadata dicts emitted by the LLM in
`regenerate_metadata_with_vocab.py` (or anything else) so they comply with
the field requirements Google enforces for rich results.

Decisions baked in (see /Users/adrienschmidt/.claude/plans/sunny-hugging-moore.md):
  - When an Article/TechArticle is missing an image, reclassify rather
    than fabricate one. The new type follows the existing shape of the
    dict (FAQPage if a Question is already present, HowTo if HowToStep is
    already present, else WebPage).
  - When a SoftwareApplication block lacks both operatingSystem and a
    monetization signal, collapse it to a Thing.
  - FAQPage/QAPage Questions must carry text + answerCount + an answer;
    synthesize the answer from the wrapper's description when possible,
    otherwise demote.

The function is pure and idempotent: `harden_jsonld(harden_jsonld(x)) == harden_jsonld(x)`.
"""
from __future__ import annotations

import copy
import datetime
from typing import Any, Optional

ARTICLE_TYPES = {"Article", "TechArticle", "NewsArticle", "BlogPosting"}
ARTICLE_ORPHAN_FIELDS = ("articleSection", "articleBody", "wordCount", "dateModified")


def harden_jsonld(
    metadata: Any,
    *,
    brand_name: Optional[str] = None,
    domain: Optional[str] = None,
    today: Optional[str] = None,
) -> Any:
    """Return a hardened deep copy of `metadata`.

    `today` lets tests pin the date; production callers omit it.
    """
    if not isinstance(metadata, (dict, list)):
        return metadata
    today_str = today or datetime.date.today().isoformat()
    organization = _organization(brand_name, domain) if brand_name else None
    out = copy.deepcopy(metadata)
    _walk(out, brand_name=brand_name, domain=domain, today=today_str, organization=organization)
    return out


def _organization(brand_name: str, domain: Optional[str]) -> dict:
    org = {"@type": "Organization", "name": brand_name}
    if domain:
        org["url"] = f"https://{domain}"
    return org


def _types(node: dict) -> list[str]:
    t = node.get("@type")
    if isinstance(t, list):
        return [x for x in t if isinstance(x, str)]
    if isinstance(t, str):
        return [t]
    return []


def _set_type(node: dict, new_type: str) -> None:
    node["@type"] = new_type


def _walk(node: Any, *, brand_name, domain, today, organization) -> None:
    if isinstance(node, dict):
        _harden_node(node, brand_name=brand_name, domain=domain, today=today, organization=organization)
        for v in list(node.values()):
            _walk(v, brand_name=brand_name, domain=domain, today=today, organization=organization)
    elif isinstance(node, list):
        for v in node:
            _walk(v, brand_name=brand_name, domain=domain, today=today, organization=organization)


def _harden_node(node: dict, *, brand_name, domain, today, organization) -> None:
    types = _types(node)
    if any(t in ARTICLE_TYPES for t in types):
        _harden_article(node, brand_name=brand_name, domain=domain, today=today, organization=organization)
        # After possible demotion, fall through so the new type's rules apply
        types = _types(node)
    if "SoftwareApplication" in types:
        _harden_software_application(node, brand_name=brand_name)
        types = _types(node)
    if any(t in ("FAQPage", "QAPage") for t in types):
        _harden_faq_or_qa_page(node)


# --- Article ---------------------------------------------------------------

def _has_image(node: dict) -> bool:
    img = node.get("image")
    if img in (None, "", []):
        return False
    return True


def _harden_article(node: dict, *, brand_name, domain, today, organization) -> None:
    if _has_image(node):
        # Fill recommended fields; the page IS eligible for Article rich result.
        if "author" not in node and organization is not None:
            node["author"] = copy.deepcopy(organization)
        dp = node.get("datePublished")
        if dp in (None, "", "null"):
            node["datePublished"] = today
            node.setdefault("contentFreshness", "assumed-current")
        if "publisher" not in node and organization is not None:
            node["publisher"] = copy.deepcopy(organization)
        return

    # No image: reclassify based on existing shape.
    if _has_question(node):
        _set_type(node, "FAQPage")
        _strip(node, ARTICLE_ORPHAN_FIELDS)
        # FAQPage Question hardening is applied in the second pass via _harden_faq_or_qa_page
        return
    if _has_howto(node):
        _set_type(node, "HowTo")
        _strip(node, ARTICLE_ORPHAN_FIELDS)
        _ensure_howto_name(node)
        return
    _set_type(node, "WebPage")
    _strip(node, ARTICLE_ORPHAN_FIELDS)


def _has_question(node: dict) -> bool:
    me = node.get("mainEntity")
    if isinstance(me, dict):
        return me.get("@type") == "Question"
    if isinstance(me, list):
        return any(isinstance(x, dict) and x.get("@type") == "Question" for x in me)
    return False


def _has_howto(node: dict) -> bool:
    me = node.get("mainEntity")
    if isinstance(me, dict) and me.get("@type") == "HowTo":
        return True
    # Any HowToStep anywhere in the dict counts as evidence of HowTo shape
    return _contains_type(node, "HowToStep")


def _contains_type(value: Any, target_type: str) -> bool:
    if isinstance(value, dict):
        if value.get("@type") == target_type:
            return True
        return any(_contains_type(v, target_type) for v in value.values())
    if isinstance(value, list):
        return any(_contains_type(v, target_type) for v in value)
    return False


def _ensure_howto_name(node: dict) -> None:
    if not node.get("name"):
        if node.get("headline"):
            node["name"] = node["headline"]


def _strip(node: dict, keys) -> None:
    for k in keys:
        node.pop(k, None)


# --- SoftwareApplication ---------------------------------------------------

def _harden_software_application(node: dict, *, brand_name) -> None:
    has_os = "operatingSystem" in node and node["operatingSystem"] not in (None, "")
    has_monetization = any(k in node and node[k] not in (None, "", [], {}) for k in ("offers", "aggregateRating", "review"))
    if has_os and has_monetization:
        return
    # Collapse to Thing — keep name only.
    name = node.get("name") or brand_name or "Software"
    keys = list(node.keys())
    for k in keys:
        if k not in ("name",):
            del node[k]
    node["@type"] = "Thing"
    node["name"] = name


# --- FAQPage / QAPage ------------------------------------------------------

def _harden_faq_or_qa_page(node: dict) -> None:
    description = node.get("description") or ""
    me = node.get("mainEntity")
    if me is None:
        # No mainEntity at all → demote to WebPage
        _demote_to_webpage(node)
        return
    is_list = isinstance(me, list)
    questions = me if is_list else [me]
    out_questions = []
    any_incomplete = False
    for q in questions:
        if not isinstance(q, dict) or q.get("@type") != "Question":
            out_questions.append(q)
            continue
        new_q = _harden_question(q, page_description=description)
        if new_q is None:
            any_incomplete = True
        else:
            out_questions.append(new_q)
    if any_incomplete and not out_questions:
        _demote_to_webpage(node)
        return
    if any_incomplete:
        # At least one Question survived; drop the incomplete ones, keep page as FAQPage/QAPage
        pass
    if is_list:
        node["mainEntity"] = out_questions
    else:
        node["mainEntity"] = out_questions[0] if out_questions else None
        if node["mainEntity"] is None:
            _demote_to_webpage(node)


def _harden_question(q: dict, *, page_description: str) -> Optional[dict]:
    """Return a hardened Question dict, or None if it can't be made complete."""
    new_q = dict(q)
    # Ensure text (= name)
    if "text" not in new_q:
        if not new_q.get("name"):
            return None  # Can't even name the question
        new_q = _insert_after(new_q, "name", "text", new_q["name"])
    # Ensure acceptedAnswer (or suggestedAnswer)
    has_answer = "acceptedAnswer" in new_q or "suggestedAnswer" in new_q
    if not has_answer:
        if not page_description:
            return None  # Can't synthesize an answer
        new_q["acceptedAnswer"] = {"@type": "Answer", "text": page_description}
    # Ensure answerCount (placed before acceptedAnswer for readability)
    if "answerCount" not in new_q:
        new_q = _insert_before(new_q, "acceptedAnswer", "answerCount", 1)
    return new_q


def _insert_after(d: dict, anchor: str, key: str, value) -> dict:
    new = {}
    placed = False
    for k, v in d.items():
        new[k] = v
        if k == anchor and not placed:
            new[key] = value
            placed = True
    if not placed:
        new[key] = value
    return new


def _insert_before(d: dict, anchor: str, key: str, value) -> dict:
    new = {}
    placed = False
    for k, v in d.items():
        if k == anchor and not placed:
            new[key] = value
            placed = True
        new[k] = v
    if not placed:
        new[key] = value
    return new


def _demote_to_webpage(node: dict) -> None:
    node["@type"] = "WebPage"
    _strip(node, ("mainEntity", "answerCount"))
