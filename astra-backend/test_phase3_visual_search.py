"""Isolated image-search validation and fusion tests; no app bootstrap or commerce DB."""
import asyncio
import struct
import zlib

from fastapi import HTTPException, UploadFile
import pytest

from app.schemas.requests import ExploreSearchRequest, QueryType
from app.services import explore
from app.services.vision import VisionResult


def _png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        payload = kind + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )


def _file(data: bytes, content_type: str = "image/png", filename: str = "dress.png") -> UploadFile:
    from io import BytesIO
    return UploadFile(filename=filename, file=BytesIO(data), headers={"content-type": content_type})


def test_malformed_image_is_rejected():
    with pytest.raises(HTTPException) as error:
        asyncio.run(explore.extract_image_features(_file(b"not an image")))
    assert error.value.status_code == 422


def test_spoofed_image_mime_is_rejected():
    with pytest.raises(HTTPException) as error:
        asyncio.run(explore.extract_image_features(_file(_png(), "image/jpeg")))
    assert error.value.status_code == 415


def test_oversized_image_is_rejected():
    oversized = b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024)
    with pytest.raises(HTTPException) as error:
        asyncio.run(explore.extract_image_features(_file(oversized)))
    assert error.value.status_code == 413


def test_vision_failure_falls_back_to_text_search_without_filename_inference(monkeypatch):
    monkeypatch.setattr(explore.vision_service, "analyze_image", lambda *_args: None)
    result = asyncio.run(explore.extract_image_features(_file(_png(), filename="laptop.png")))
    assert result.query == ""
    assert result.labels == []

    products = [{
        "id": "blue-dress", "title": "Blue Formal Dress", "category": "Clothing & Fashion",
        "description": "", "search_terms": "blue formal dress", "semantic_tags": ["formal"],
        "trust": 90, "rating": 4.5, "price": 4000, "image_url": "", "seller_name": "Demo",
        "is_verified_seller": True, "total_reviews": 1, "badge": None,
        "availability": "in_stock", "stock_count": 3,
    }]
    monkeypatch.setattr(explore.product_repository, "list_products", lambda: products)
    response = asyncio.run(explore.execute_search(
        ExploreSearchRequest(query_type=QueryType.MULTIMODAL, text_query="blue formal dress under 5000"),
        None, _file(_png(), filename="laptop.png"),
    ))
    assert [item["id"] for item in response.results] == ["blue-dress"]
    assert response.image_labels == []


def test_visual_ranking_and_reasons_are_grounded_in_catalog_fields(monkeypatch):
    products = [
        {"id": "blue-dress", "title": "Blue Formal Dress", "category": "Clothing & Fashion",
         "description": "", "search_terms": "blue formal dress", "semantic_tags": ["formal"],
         "trust": 90, "rating": 4.5, "price": 4000, "image_url": "", "seller_name": "Demo",
         "is_verified_seller": True, "total_reviews": 1, "badge": None,
         "availability": "in_stock", "stock_count": 3},
        {"id": "red-shirt", "title": "Red Shirt", "category": "Clothing & Fashion",
         "description": "", "search_terms": "red shirt", "semantic_tags": [],
         "trust": 90, "rating": 4.5, "price": 3000, "image_url": "", "seller_name": "Demo",
         "is_verified_seller": True, "total_reviews": 1, "badge": None,
         "availability": "in_stock", "stock_count": 3},
    ]
    monkeypatch.setattr(explore.product_repository, "list_products", lambda: products)
    monkeypatch.setattr(explore.vision_service, "analyze_image", lambda *_args: VisionResult(
        labels=["blue", "formal", "dress"], query="blue formal dress", confidence=0.8, provider="groq",
    ))
    response = asyncio.run(explore.execute_search(
        ExploreSearchRequest(query_type=QueryType.MULTIMODAL, text_query="dress under 5000"),
        None, _file(_png()),
    ))
    assert response.results[0]["id"] == "blue-dress"
    reasons = response.results[0]["match_reasons"]
    assert any('"blue"' in reason and "title" in reason for reason in reasons)
    assert any('"formal"' in reason and "catalog title" in reason for reason in reasons)
    assert not any("red" in reason.lower() for reason in reasons)


def test_image_analysis_is_dispatched_off_event_loop(monkeypatch):
    observed = {}
    def analyze(*_args):
        import threading
        observed["thread"] = threading.current_thread().name
        return None
    monkeypatch.setattr(explore.vision_service, "analyze_image", analyze)
    asyncio.run(explore.extract_image_features(_file(_png())))
    assert observed["thread"] != "MainThread"


def test_vision_provider_descriptors_are_parsed_without_network(monkeypatch):
    from app.services import vision

    monkeypatch.setattr(vision, "_request_vision_completion", lambda *_args, **_kwargs: (
        '{"category":"dress","color":"blue","style":"formal","pattern":"solid",'
        '"keywords":["evening wear"]}'
    ))
    result = vision.analyze_image(_png())
    assert result is not None
    assert result.labels == ["dress", "blue", "formal", "solid", "evening wear"]
    assert result.provider == "groq"
