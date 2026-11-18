import base64
from io import BytesIO
from typing import Annotated
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from backend import prep_materials
from backend.models import User


@pytest.fixture()
def client():
    scheme = HTTPBearer(auto_error=False)

    def authenticate(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(scheme)]):
        if credentials is None:
            raise HTTPException(401)
        return User(id=1)

    app = FastAPI()
    app.include_router(prep_materials.build_material_router(authenticate), prefix="/api/v1")
    return TestClient(app)


def upload(client, filename, raw):
    return client.post("/api/v1/prep/materials/extract", headers={"Authorization": "Bearer test"}, json={
        "filename": filename, "contentBase64": base64.b64encode(raw).decode("ascii"),
    })


def make_pdf(text=None):
    output = BytesIO()
    with PdfWriter() as writer:
        page = writer.add_blank_page(width=200, height=200)
        if text:
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({
                    NameObject("/F1"): DictionaryObject({
                        NameObject("/Type"): NameObject("/Font"),
                        NameObject("/Subtype"): NameObject("/Type1"),
                        NameObject("/BaseFont"): NameObject("/Helvetica"),
                    }),
                }),
            })
            content = DecodedStreamObject()
            content.set_data(b"BT /F1 12 Tf 40 40 Td (" + text + b") Tj ET")
            page[NameObject("/Contents")] = content
        writer.write(output)
    return output.getvalue()


def make_docx(xml):
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


def test_requires_authentication_and_rejects_unsupported_files(client):
    assert client.post("/api/v1/prep/materials/extract", json={}).status_code == 401
    assert upload(client, "教材.xlsx", b"invalid").status_code == 415
    assert upload(client, "教材.pdf", b"invalid").status_code == 422


def test_pdf_extracts_text_and_redirects_empty_scans(client):
    result = upload(client, "教材.pdf", make_pdf(b"Observe the water droplets."))
    assert result.status_code == 200, result.text
    assert result.json() == {"filename": "教材.pdf", "text": "Observe the water droplets.", "truncated": False}
    result = upload(client, "扫描.pdf", make_pdf())
    assert result.status_code == 422
    assert "OCR" in result.json()["detail"]


def test_docx_preserves_paragraphs_and_disallows_entities(client):
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>观察水滴</w:t></w:r></w:p>'
        '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>记录</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
        '</w:body></w:document>'
    )
    result = upload(client, r'C:\教案\课程.docx', make_docx(document))
    assert result.status_code == 200, result.text
    assert result.json() == {"filename": "课程.docx", "text": "观察水滴\n记录", "truncated": False}
    entity = '<!DOCTYPE w:document [<!ENTITY blocked "example">]>' + document
    assert upload(client, "恶意文档.docx", make_docx(entity)).status_code == 422


def test_limits_extracted_characters_and_rejects_large_request(client, monkeypatch):
    result = upload(client, "教案.txt", ("科学" * (prep_materials.MAX_TEXT + 1)).encode())
    assert result.status_code == 200
    assert len(result.json()["text"]) == prep_materials.MAX_TEXT
    assert result.json()["truncated"] is True
    monkeypatch.setattr(prep_materials, "MAX_BODY", 256)
    assert upload(client, "教案.txt", b"a" * 257).status_code == 413


def test_photo_extraction_validates_image_and_keeps_unclear_text(client, monkeypatch):
    async def fake_provider(_key, model, messages, **_options):
        assert model == "deepseek-flash"
        assert messages[-1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        return {"title": "空气占据空间", "materials": ["透明杯", "纸巾"], "unclear": ["水量不可辨读"]}

    monkeypatch.setattr(prep_materials, "request_deepseek_json", fake_provider)
    endpoint = "/api/v1/prep/materials/extract-image"
    headers = {"Authorization": "Bearer test"}
    assert client.post(endpoint, json={}).status_code == 401
    assert client.post(endpoint, headers=headers, json={
        "filename": "教材.jpg", "contentBase64": "AAAA",
    }).status_code == 422
    data = BytesIO()
    Image.new("RGB", (32, 32)).save(data, format="JPEG")
    result = client.post(endpoint, headers=headers, json={
        "filename": "教材.jpg", "contentBase64": base64.b64encode(data.getvalue()).decode(),
    })
    assert result.status_code == 200, result.text
    assert "实验器材\n• 透明杯\n• 纸巾" in result.json()["text"]
    assert "待核对\n• 水量不可辨读" in result.json()["text"]
