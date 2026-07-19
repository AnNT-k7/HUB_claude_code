from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_pipeline_renderer_uses_progressive_visibility_contract() -> None:
    javascript = (REPOSITORY_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    stylesheet = (REPOSITORY_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for state_class in ("is-revealed", "is-active", "is-complete"):
        assert f"node.classList.toggle('{state_class}'" in javascript
        assert f".pipeline-node.{state_class}" in stylesheet

    assert "renderPipelineConnections" in javascript
    assert "schedulePipelineConnections" in javascript
    assert "['recommendationNode', 'humanNode']" in javascript
    assert "['humanNode', 'executorNode']" in javascript


def test_pipeline_svg_has_a_render_target() -> None:
    html = (REPOSITORY_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert 'id="flowCanvas"' in html
    assert 'id="edgeLayer"' in html
    assert 'id="underwriterNode"' in html
    assert 'id="systemsNode"' in html


def test_five_mock_system_outputs_are_clickable_and_mapped() -> None:
    html = (REPOSITORY_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (REPOSITORY_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    for system in ("los", "dms", "workflow", "notification", "audit"):
        assert f'data-system-output="{system}"' in html
        assert f"{system}: {{" in javascript

    assert 'id="systemOutputModal"' in html
    assert "UPDATE_INCOME_DRAFT" in javascript
    assert "ATTACH_EVIDENCE" in javascript
    assert "CREATE_EXCEPTION_TASK" in javascript
    assert "REQUEST_DOCUMENTS" in javascript
    assert "function openSystemOutput" in javascript


def test_create_case_form_auto_generates_customer_reference_and_uploads_mvp_documents() -> None:
    html = (REPOSITORY_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (REPOSITORY_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'class="modal glass-panel case-form create-case-form"' in html
    assert 'name="customer_code"' not in html
    for document_type in (
        "LOAN_APPLICATION",
        "EMPLOYMENT_CONTRACT",
        "PAYSLIP_BUNDLE",
        "BANK_STATEMENT",
    ):
        assert f'data-document-type="{document_type}"' in html

    assert "function pendingCaseDocuments" in javascript
    assert "function uploadPendingCaseDocuments" in javascript
    assert "await uploadPendingCaseDocuments(created.id, documents)" in javascript
