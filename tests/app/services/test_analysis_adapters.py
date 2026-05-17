"""Unit tests for document analysis provider adapters.

Each test calls the module-level _adapt() function directly with fixture data,
so no live API calls are made. Tests assert on the AnalysisResult output only —
not on internal maps or iteration order.
"""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Textract
# ---------------------------------------------------------------------------


def _textract_adapt(response: dict):
    from app.services.analysis.textract import _adapt

    return _adapt(response)


def _load_textract_fixture() -> dict:
    raw = json.loads((FIXTURES_DIR / "aws_textract_credit_card.json").read_text())
    # The fixture file is the full asset response; raw_response holds the
    # Textract API payload that _adapt() expects.
    return raw["extracted_data"]["raw_response"]


class TestTextractAdapt:
    def test_canonical_fields_present(self):
        result = _textract_adapt(_load_textract_fixture())
        assert result.fields["given_names"].value == "EMILIANO"
        assert result.fields["surname"].value == "JANKOWSKI"
        assert result.fields["middle_name"].value == "RUBEN"

    def test_unmapped_fields_passed_through(self):
        result = _textract_adapt(_load_textract_fixture())
        # CITY_IN_ADDRESS maps to "city", STATE_IN_ADDRESS to "state"
        assert "city" in result.fields
        assert result.fields["city"].value == "CADUCA"
        assert "state" in result.fields
        assert result.fields["state"].value == "CA"

    def test_empty_value_fields_excluded(self):
        result = _textract_adapt(_load_textract_fixture())
        # Many fields (EXPIRATION_DATE, DOCUMENT_NUMBER, etc.) have empty Text in
        # the fixture — they must not appear in fields.
        for field_value in result.fields.values():
            assert field_value.value is not None
            assert field_value.value.strip() != ""

    def test_document_type_driver_license_front(self):
        result = _textract_adapt(_load_textract_fixture())
        # Textract returns "DRIVER LICENSE FRONT"; prefix match should give "drivers_license"
        assert result.document_type == "drivers_license"

    def test_document_type_confidence(self):
        result = _textract_adapt(_load_textract_fixture())
        assert 0.0 < result.document_type_confidence <= 1.0

    def test_ocr_lines_populated(self):
        result = _textract_adapt(_load_textract_fixture())
        assert len(result.ocr_lines) > 0
        texts = [line.text for line in result.ocr_lines]
        assert "EMILIANO RUBEN JANKOWSKI" in texts

    def test_ocr_lines_contain_card_number(self):
        result = _textract_adapt(_load_textract_fixture())
        texts = [line.text for line in result.ocr_lines]
        assert "4273 6706 0864 7972" in texts

    def test_ocr_lines_contain_expiry(self):
        result = _textract_adapt(_load_textract_fixture())
        texts = [line.text for line in result.ocr_lines]
        assert "10/25" in texts

    def test_ocr_line_confidence_normalised(self):
        result = _textract_adapt(_load_textract_fixture())
        for line in result.ocr_lines:
            assert 0.0 <= line.confidence <= 1.0

    def test_no_partial_field(self):
        result = _textract_adapt(_load_textract_fixture())
        assert not hasattr(result, "partial")

    def test_provider(self):
        result = _textract_adapt(_load_textract_fixture())
        assert result.provider == "textract"

    def test_empty_identity_documents_returns_unknown(self):
        result = _textract_adapt({"IdentityDocuments": []})
        assert result.document_type == "unknown"
        assert result.fields == {}
        assert result.ocr_lines == []

    def test_unknown_id_type_snake_cased(self):
        response = {
            "IdentityDocuments": [
                {
                    "IdentityDocumentFields": [
                        {
                            "Type": {"Text": "ID_TYPE"},
                            "ValueDetection": {"Text": "SOME EXOTIC CARD", "Confidence": 80.0},
                        }
                    ],
                    "Blocks": [],
                }
            ]
        }
        result = _textract_adapt(response)
        assert result.document_type == "some_exotic_card"


# ---------------------------------------------------------------------------
# Google DAI
# ---------------------------------------------------------------------------


def _google_dai_adapt(doc):
    from app.services.analysis.google_dai import _adapt

    return _adapt(doc)


class _FakeEntity:
    def __init__(self, type_: str, mention_text: str, confidence: float = 0.95):
        self.type_ = type_
        self.mention_text = mention_text
        self.confidence = confidence


class _FakeDoc:
    def __init__(self, entities, text: str = ""):
        self.entities = entities
        self.text = text


class TestGoogleDAIAdapt:
    def test_canonical_fields_mapped(self):
        doc = _FakeDoc(
            entities=[
                _FakeEntity("document_type", "passport"),
                _FakeEntity("given_names", "ANNA"),
                _FakeEntity("family_name", "SMITH"),
                _FakeEntity("date_of_birth", "1990-01-15"),
            ]
        )
        result = _google_dai_adapt(doc)
        assert result.fields["given_names"].value == "ANNA"
        assert result.fields["surname"].value == "SMITH"
        assert result.fields["date_of_birth"].value == "1990-01-15"

    def test_document_type_mapped(self):
        doc = _FakeDoc(entities=[_FakeEntity("document_type", "passport")])
        result = _google_dai_adapt(doc)
        assert result.document_type == "passport"

    def test_unmapped_entity_type_passes_through(self):
        doc = _FakeDoc(
            entities=[
                _FakeEntity("mrz_code", "P<UTOERIKSSON<<ANNA<MARIA"),
            ]
        )
        result = _google_dai_adapt(doc)
        assert "mrz_code" in result.fields
        assert result.fields["mrz_code"].value == "P<UTOERIKSSON<<ANNA<MARIA"

    def test_empty_mention_text_excluded(self):
        doc = _FakeDoc(entities=[_FakeEntity("given_names", "")])
        result = _google_dai_adapt(doc)
        assert "given_names" not in result.fields

    def test_ocr_lines_from_document_text(self):
        doc = _FakeDoc(
            entities=[],
            text="ANNA SMITH\n1990-01-15\nPASSPORT",
        )
        result = _google_dai_adapt(doc)
        texts = [line.text for line in result.ocr_lines]
        assert "ANNA SMITH" in texts
        assert "PASSPORT" in texts

    def test_ocr_lines_empty_when_no_text(self):
        doc = _FakeDoc(entities=[], text="")
        result = _google_dai_adapt(doc)
        assert result.ocr_lines == []

    def test_provider(self):
        doc = _FakeDoc(entities=[])
        result = _google_dai_adapt(doc)
        assert result.provider == "google_dai"

    def test_unknown_document_type_passes_through(self):
        doc = _FakeDoc(entities=[_FakeEntity("document_type", "some_new_type")])
        result = _google_dai_adapt(doc)
        assert result.document_type == "some_new_type"


# ---------------------------------------------------------------------------
# Claude Vision
# ---------------------------------------------------------------------------


def _claude_adapt(raw: dict):
    from app.services.analysis.claude_vision import _adapt

    return _adapt(raw)


class TestClaudeVisionAdapt:
    def _raw(self, **kwargs) -> dict:
        base = {
            "document_type": "passport",
            "document_type_confidence": 0.97,
            "fields": {
                "surname": {"value": "JONES", "confidence": 0.99},
                "given_names": {"value": "ALICE", "confidence": 0.98},
                "date_of_birth": {"value": "1985-03-22", "confidence": 0.95},
            },
            "ocr_lines": [
                {"text": "ALICE JONES", "confidence": 0.99},
                {"text": "1985-03-22", "confidence": 0.95},
            ],
        }
        base.update(kwargs)
        return base

    def test_fields_extracted(self):
        result = _claude_adapt(self._raw())
        assert result.fields["surname"].value == "JONES"
        assert result.fields["given_names"].value == "ALICE"

    def test_document_type(self):
        result = _claude_adapt(self._raw())
        assert result.document_type == "passport"

    def test_document_type_confidence(self):
        result = _claude_adapt(self._raw())
        assert result.document_type_confidence == pytest.approx(0.97)

    def test_ocr_lines_populated(self):
        result = _claude_adapt(self._raw())
        texts = [line.text for line in result.ocr_lines]
        assert "ALICE JONES" in texts

    def test_null_value_excluded(self):
        raw = self._raw()
        raw["fields"]["middle_name"] = {"value": None, "confidence": 0.5}
        result = _claude_adapt(raw)
        assert "middle_name" not in result.fields

    def test_empty_string_value_excluded(self):
        raw = self._raw()
        raw["fields"]["suffix"] = {"value": "  ", "confidence": 0.9}
        result = _claude_adapt(raw)
        assert "suffix" not in result.fields

    def test_empty_ocr_line_excluded(self):
        raw = self._raw()
        raw["ocr_lines"].append({"text": "", "confidence": 0.9})
        result = _claude_adapt(raw)
        for line in result.ocr_lines:
            assert line.text.strip() != ""

    def test_missing_ocr_lines_key(self):
        raw = self._raw()
        del raw["ocr_lines"]
        result = _claude_adapt(raw)
        assert result.ocr_lines == []

    def test_provider(self):
        result = _claude_adapt(self._raw())
        assert result.provider == "claude"

    def test_arbitrary_field_names_pass_through(self):
        raw = self._raw()
        raw["fields"]["card_number"] = {"value": "4273 6706 0864 7972", "confidence": 0.99}
        result = _claude_adapt(raw)
        assert result.fields["card_number"].value == "4273 6706 0864 7972"
