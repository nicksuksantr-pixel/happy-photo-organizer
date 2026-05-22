"""
analyzer.py — Gemini Vision wrapper
ส่งรูป + ชื่องานใน catalog → ได้ชื่องานที่ match ที่สุด (+ confidence + suggestion ถ้าไม่ match)
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from google.genai import types

from .auth import create_client, get_model
from .image_io import get_mime_type
from .rate_limiter import QuotaExceededError, _CancelledError, get_rate_limiter


def _cancelled_result(n: int = 0) -> dict:
    return {
        "matched_name": None,
        "suggested_name": None,
        "confidence": 0.0,
        "reasoning": "cancelled",
        "sample_count": 0,
        "total_in_group": n,
    }

ANALYZER_SYSTEM_PROMPT = """You are an AI assistant that categorizes maintenance and repair photos
from commercial vessels (ship engineering work).

Your task: look at the image(s) and identify which "job" from the provided list best matches.

Rules:
1. If you are confident the image matches a job in the list → set matched_name to the EXACT name from the list
2. If no job in the list matches → set matched_name = null AND suggested_name = a new SHORT English job title
   (use technical verbs like Cleaned/Repaired/Replaced/Inspected/Installed; keep under 60 chars)
3. confidence = 0.0–1.0 (1.0 = very confident)
4. reasoning = a brief ENGLISH description of what you see (1 sentence, under 200 chars)

Respond ONLY as a single JSON object (NOT an array, NOT wrapped in markdown). Schema:
{
  "matched_name": "..." | null,
  "suggested_name": "..." | null,
  "confidence": 0.0-1.0,
  "reasoning": "..."
}"""


def _build_user_prompt(catalog_names: list[str]) -> str:
    names_block = "\n".join(f"- {n}" for n in catalog_names)
    return f"""Available jobs in catalog:
{names_block}

Examine the image(s) above and respond as a single JSON object per the schema."""


def _parse_json_response(text: str) -> dict:
    """Gemini อาจ wrap JSON ใน ```json ... ``` หรือคืน list — normalize เป็น dict เสมอ"""
    text = (text or "").strip()

    def _coerce_to_dict(parsed):
        """ถ้า parsed เป็น list → เอา element แรกที่เป็น dict; ถ้าเป็น dict → return ตรงๆ"""
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    return item
        return None

    # 1) parse ตรงๆ
    try:
        parsed = json.loads(text)
        d = _coerce_to_dict(parsed)
        if d is not None:
            return d
    except Exception:
        pass
    # 2) regex หา JSON block (รองรับทั้ง {} และ [])
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            continue
        try:
            parsed = json.loads(match.group(0))
            d = _coerce_to_dict(parsed)
            if d is not None:
                return d
        except Exception:
            continue
    return {
        "matched_name": None,
        "suggested_name": None,
        "confidence": 0.0,
        "reasoning": f"parse error: {text[:200]}",
    }


def analyze_image(
    image_path: Path,
    catalog_names: list[str],
    *,
    client=None,
    model: str | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:
    """
    ส่งรูป 1 ใบให้ Gemini พิจารณา → คืน dict ตาม schema
    """
    if cancel_event is not None and cancel_event.is_set():
        return _cancelled_result()
    if client is None:
        client, err = create_client()
        if err:
            return {"matched_name": None, "suggested_name": None, "confidence": 0.0, "reasoning": err}

    model_name = model or get_model()

    limiter = get_rate_limiter()
    try:
        with limiter.call("analyze", cancel_event=cancel_event) as ctx:
            image_bytes = Path(image_path).read_bytes()
            mime = get_mime_type(Path(image_path))
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime),
                    _build_user_prompt(catalog_names),
                ],
                config=types.GenerateContentConfig(
                    system_instruction=ANALYZER_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            # token usage (best-effort)
            try:
                usage = getattr(response, "usage_metadata", None)
                if usage:
                    ctx.tokens = int(getattr(usage, "total_token_count", 0) or 0)
            except Exception:
                pass
            text = response.text or ""
        result = _parse_json_response(text)
        result.setdefault("matched_name", None)
        result.setdefault("suggested_name", None)
        result.setdefault("confidence", 0.0)
        result.setdefault("reasoning", "")
        result["confidence"] = float(result.get("confidence") or 0.0)
        return result
    except _CancelledError:
        return _cancelled_result()
    except QuotaExceededError as qe:
        return {
            "matched_name": None,
            "suggested_name": None,
            "confidence": 0.0,
            "reasoning": f"quota exceeded: {qe}",
        }
    except Exception as e:
        return {
            "matched_name": None,
            "suggested_name": None,
            "confidence": 0.0,
            "reasoning": f"error: {str(e)[:200]}",
        }


def analyze_group(
    image_paths: list[Path],
    catalog_names: list[str],
    *,
    client=None,
    model: str | None = None,
    sample_size: int = 3,
    cancel_event: threading.Event | None = None,
) -> dict:
    """
    วิเคราะห์กลุ่มรูป (เช่นรูปหลายใบของงานเดียวกัน) — ส่ง sample ไม่กี่ใบไป Gemini เพื่อประหยัด quota
    คืน result เดียวที่เป็นตัวแทนของกลุ่ม
    """
    if cancel_event is not None and cancel_event.is_set():
        return _cancelled_result(len(image_paths))
    if client is None:
        client, err = create_client()
        if err:
            return {"matched_name": None, "suggested_name": None, "confidence": 0.0, "reasoning": err}

    # เอาตัวอย่างไม่เกิน sample_size ใบ — first, middle, last
    n = len(image_paths)
    if n == 0:
        return {"matched_name": None, "suggested_name": None, "confidence": 0.0, "reasoning": "no images"}
    if n <= sample_size:
        samples = image_paths
    else:
        indices = sorted({0, n // 2, n - 1})
        if len(indices) < sample_size:
            indices = sorted({0, n // 4, n // 2, 3 * n // 4, n - 1})[:sample_size]
        samples = [image_paths[i] for i in indices]

    model_name = model or get_model()
    limiter = get_rate_limiter()
    try:
        with limiter.call("analyze_group", cancel_event=cancel_event) as ctx:
            if cancel_event is not None and cancel_event.is_set():
                return _cancelled_result(n)
            parts = []
            for p in samples:
                mime = get_mime_type(Path(p))
                parts.append(types.Part.from_bytes(data=Path(p).read_bytes(), mime_type=mime))
            parts.append(
                _build_user_prompt(catalog_names)
                + f"\n\n(The {len(samples)} image(s) above are samples from {n} photos of the same job — review together.)"
            )

            response = client.models.generate_content(
                model=model_name,
                contents=parts,
                config=types.GenerateContentConfig(
                    system_instruction=ANALYZER_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            try:
                usage = getattr(response, "usage_metadata", None)
                if usage:
                    ctx.tokens = int(getattr(usage, "total_token_count", 0) or 0)
            except Exception:
                pass

        result = _parse_json_response(response.text or "")
        result.setdefault("matched_name", None)
        result.setdefault("suggested_name", None)
        result.setdefault("confidence", 0.0)
        result.setdefault("reasoning", "")
        result["confidence"] = float(result.get("confidence") or 0.0)
        result["sample_count"] = len(samples)
        result["total_in_group"] = n
        return result
    except _CancelledError:
        return _cancelled_result(n)
    except QuotaExceededError as qe:
        return {
            "matched_name": None,
            "suggested_name": None,
            "confidence": 0.0,
            "reasoning": f"quota exceeded: {qe}",
            "sample_count": 0,
            "total_in_group": n,
        }
    except Exception as e:
        return {
            "matched_name": None,
            "suggested_name": None,
            "confidence": 0.0,
            "reasoning": f"error: {str(e)[:200]}",
            "sample_count": 0,
            "total_in_group": n,
        }
