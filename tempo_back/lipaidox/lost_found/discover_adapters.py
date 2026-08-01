"""
Reshapes raw `lost_found` service output into the exact TS result shapes the
/discover frontend expects (see interfaces in app/discover/page.tsx). Each
function returns None when the underlying service couldn't produce a usable
result, so the view can report a gap instead of forwarding empty/error data.
"""

from typing import Dict, List, Optional


_QR_TYPE_MAP = {
    "url": "url",
    "email": "contact",
    "phone": "contact",
    "sms": "contact",
    "vcard": "contact",
    "wifi": "wifi",
    "location": "url",
    "text": "url",
}

_QR_ACTIONS = [
    {"label": "Open Link", "icon": "external"},
    {"label": "Copy", "icon": "copy"},
    {"label": "Save", "icon": "bookmark"},
    {"label": "Report", "icon": "flag"},
]


def adapt_qr(raw: Dict) -> Dict:
    codes = raw.get("codes") or []
    if raw.get("status") != "success" or not codes:
        return {
            "type": "url",
            "title": "No Code Detected",
            "content": "No QR code or barcode was found in this image",
            "data": {"Status": "Not Found"},
            "actions": [{"label": "Try Again", "icon": "refresh"}],
        }

    code = codes[0]
    content = code.get("content", "")
    data_type = code.get("data_type", "text")
    parsed = code.get("parsed_content") or {}
    parsed_data = parsed.get("data") or {}

    if data_type == "url":
        data = {"URL": content, "Type": "Website Link", "Safe": "Unknown"}
    elif parsed_data:
        data = {str(k).replace("_", " ").title(): str(v) for k, v in parsed_data.items()}
    else:
        data = {"Content": content}

    return {
        "type": _QR_TYPE_MAP.get(data_type, "url"),
        "title": f"{data_type.replace('_', ' ').title()} Code Detected",
        "content": content,
        "data": data,
        "actions": _QR_ACTIONS,
        "securityStatus": "Unknown",
    }


def adapt_price(raw: Dict, product_name: str, category: str) -> Optional[Dict]:
    if raw.get("status") not in ("success", "cached"):
        return None

    price_data = raw.get("prices") or {}
    summary = price_data.get("summary") or {}
    sources = price_data.get("sources") or {}

    prices: List[Dict] = []
    for store, info in sources.items():
        for product in (info.get("products") or [])[:1]:
            prices.append({
                "store": store,
                "logo": "",
                "price": product.get("price", 0),
                "currency": product.get("currency", "USD"),
                "shipping": "",
                "rating": 0,
                "inStock": True,
                "url": "#",
            })

    if not prices:
        return None

    return {
        "productName": product_name,
        "category": category or "",
        "image": "",
        "prices": prices,
        "priceHistory": [],
        "lowestPrice": summary.get("lowest_price", 0),
        "highestPrice": summary.get("highest_price", 0),
        "avgPrice": summary.get("average_price", 0),
    }


def adapt_deepfake(raw: Dict) -> Optional[Dict]:
    if raw.get("status") != "success":
        return None

    fallback = raw.get("fallback_analyses") or {}
    face = fallback.get("face_consistency") or {}
    confidence = raw.get("confidence_score", raw.get("deepfake_score", 0))
    is_deepfake = bool(raw.get("is_deepfake", False))

    details = []
    if face:
        details.append({
            "area": "Face Consistency",
            "confidence": face.get("confidence", 0),
            "type": "Face Swap" if face.get("is_suspicious") else "Clean",
        })

    method = raw.get("method", "fallback").title()
    outcome = "manipulation indicators detected" if is_deepfake else "no significant manipulation detected"

    return {
        "isDeepfake": is_deepfake,
        "confidence": confidence,
        "faceAnalysis": {
            "facesDetected": face.get("faces_detected", 0),
            "manipulatedFaces": 1 if face.get("is_suspicious") else 0,
            "details": details,
        },
        "frameAnalysis": {
            "totalFrames": 1,
            "suspiciousFrames": 1 if is_deepfake else 0,
            "artifacts": raw.get("artifacts", []),
        },
        "verdict": f"{method} analysis: {outcome} ({confidence}% confidence).",
    }


def adapt_community(consensus: Dict, expert_verdict: Optional[Dict]) -> Dict:
    vote_stats = consensus.get("vote_statistics") or {}

    result = {
        "totalVotes": consensus.get("total_votes", 0),
        "realVotes": (vote_stats.get("real") or {}).get("count", 0),
        "fakeVotes": (vote_stats.get("fake") or {}).get("count", 0),
        "unsureVotes": (vote_stats.get("helpful") or {}).get("count", 0),
        "expertReviewRequested": expert_verdict is not None,
        "recentVotes": [],
        "reportCount": consensus.get("total_reports", 0),
    }

    if expert_verdict:
        result["expertVerdict"] = expert_verdict

    return result
