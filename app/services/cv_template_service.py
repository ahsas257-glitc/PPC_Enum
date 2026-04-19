from __future__ import annotations

import re
import shutil
import subprocess
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from docx import Document

PLACEHOLDER_FIELDS = [
    ("surveyor_name", "Surveyor full name"),
    ("surveyor_code", "Surveyor code"),
    ("gender", "Gender"),
    ("father_name", "Father name"),
    ("tazkira_no", "Tazkira number"),
    ("email_address", "Email address"),
    ("phone_number", "Phone number"),
    ("whatsapp_number", "WhatsApp number"),
    ("permanent_province_name", "Permanent province"),
    ("current_province_name", "Current province"),
    ("cv_link", "Existing CV link"),
    ("default_bank_name", "Default bank"),
    ("default_payment_type", "Default payment type"),
    ("default_payout_value", "Default payout account or mobile"),
    ("bank_accounts", "All linked bank accounts"),
    ("assignments", "All surveyor project assignments"),
    ("active_assignments", "Only active/current project assignments"),
    ("project_names", "Project names list"),
    ("generated_date", "Document generated date"),
]

WORD_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_TEMPLATE_SIZE_BYTES = 8 * 1024 * 1024
MAX_TEMPLATE_SIZE_MB = MAX_TEMPLATE_SIZE_BYTES // (1024 * 1024)


def _display(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    return text if text else fallback


def _format_status(value: Any) -> str:
    text = _display(value)
    return text.replace("_", " ").title() if text else ""


def _format_date_range(start_value: Any, end_value: Any) -> str:
    start_text = _display(start_value, "No start date")
    end_text = _display(end_value, "Present")
    return f"{start_text} - {end_text}"


def _format_bank_account(account: dict[str, Any]) -> str:
    bank_name = _display(account.get("bank_name"), "No bank")
    payment_type = _format_status(account.get("payment_type")) or "Payment"
    payout_value = _display(account.get("account_number")) or _display(account.get("mobile_number"), "No payout value")
    account_title = _display(account.get("account_title"))
    status = "Active" if account.get("is_active") else "Inactive"
    default_marker = "Default" if account.get("is_default") else "Secondary"
    title_part = f" - {account_title}" if account_title else ""
    return f"{bank_name} - {payment_type} - {payout_value}{title_part} - {status} - {default_marker}"


def _format_assignment(assignment: dict[str, Any]) -> str:
    project_code = _display(assignment.get("project_code"))
    project_name = _display(assignment.get("project_name"), "Unnamed project")
    role = _format_status(assignment.get("role")) or "Surveyor"
    status = _format_status(assignment.get("assignment_status")) or "Unspecified"
    province = _display(assignment.get("work_province_name")) or _display(assignment.get("work_province_code"), "No province")
    date_range = _format_date_range(assignment.get("assignment_start_date"), assignment.get("assignment_end_date"))
    project_label = f"{project_code} - {project_name}" if project_code else project_name
    return f"{project_label} | {role} | {province} | {status} | {date_range}"


def _join_lines(values: list[str], fallback: str = "") -> str:
    cleaned = [value for value in values if value]
    return "\n".join(cleaned) if cleaned else fallback


def build_replacement_map(
    profile: dict[str, Any],
    bank_accounts: list[dict[str, Any]] | None = None,
    assignments: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    bank_accounts = bank_accounts or []
    assignments = assignments or []
    active_assignments = [assignment for assignment in assignments if assignment.get("is_current_active")]

    replacements = {
        "surveyor_id": _display(profile.get("surveyor_id")),
        "surveyor_code": _display(profile.get("surveyor_code")),
        "surveyor_name": _display(profile.get("surveyor_name")),
        "gender": _format_status(profile.get("gender")),
        "father_name": _display(profile.get("father_name")),
        "tazkira_no": _display(profile.get("tazkira_no")),
        "email_address": _display(profile.get("email_address")),
        "whatsapp_number": _display(profile.get("whatsapp_number")),
        "phone_number": _display(profile.get("phone_number")),
        "permanent_province_code": _display(profile.get("permanent_province_code")),
        "permanent_province_name": _display(profile.get("permanent_province_name")),
        "current_province_code": _display(profile.get("current_province_code")),
        "current_province_name": _display(profile.get("current_province_name")),
        "cv_link": _display(profile.get("cv_link")),
        "cv_file_name": _display(profile.get("cv_file_name")),
        "tazkira_image_name": _display(profile.get("tazkira_image_name")),
        "tazkira_pdf_name": _display(profile.get("tazkira_pdf_name")),
        "tazkira_word_name": _display(profile.get("tazkira_word_name")),
        "document_count": _display(profile.get("document_count"), "0"),
        "account_count": _display(profile.get("account_count"), "0"),
        "active_account_count": _display(profile.get("active_account_count"), "0"),
        "default_bank_name": _display(profile.get("default_bank_name")),
        "default_payment_type": _format_status(profile.get("default_payment_type")),
        "default_payout_value": _display(profile.get("default_payout_value")),
        "bank_names": _display(profile.get("bank_names")),
        "bank_accounts": _join_lines([_format_bank_account(account) for account in bank_accounts], "No linked bank accounts"),
        "assignments": _join_lines([_format_assignment(assignment) for assignment in assignments], "No project assignments"),
        "active_assignments": _join_lines(
            [_format_assignment(assignment) for assignment in active_assignments],
            "No active project assignments",
        ),
        "project_names": _join_lines([_display(assignment.get("project_name")) for assignment in assignments], "No project assignments"),
        "generated_date": date.today().strftime("%Y-%m-%d"),
    }
    return replacements


def replacement_tokens(replacements: dict[str, str]) -> dict[str, str]:
    return {f"{{{{{key}}}}}": value for key, value in replacements.items()}


def _replace_in_paragraph(paragraph, tokens: dict[str, str]) -> None:
    original_text = paragraph.text
    if "{{" not in original_text:
        return

    updated_text = original_text
    for token, value in tokens.items():
        updated_text = updated_text.replace(token, value)

    if updated_text == original_text:
        return

    if not paragraph.runs:
        paragraph.add_run(updated_text)
        return

    paragraph.runs[0].text = updated_text
    for run in paragraph.runs[1:]:
        run.text = ""


def _replace_in_table(table, tokens: dict[str, str]) -> None:
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                _replace_in_paragraph(paragraph, tokens)
            for nested_table in cell.tables:
                _replace_in_table(nested_table, tokens)


def _replace_in_document(document, tokens: dict[str, str]) -> None:
    for paragraph in document.paragraphs:
        _replace_in_paragraph(paragraph, tokens)
    for table in document.tables:
        _replace_in_table(table, tokens)
    for section in document.sections:
        for part in (section.header, section.footer):
            for paragraph in part.paragraphs:
                _replace_in_paragraph(paragraph, tokens)
            for table in part.tables:
                _replace_in_table(table, tokens)


def render_docx_template(template_bytes: bytes, replacements: dict[str, str]) -> bytes:
    document = Document(BytesIO(template_bytes))
    _replace_in_document(document, replacement_tokens(replacements))
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def find_unreplaced_placeholders(document_bytes: bytes) -> list[str]:
    document = Document(BytesIO(document_bytes))
    found: set[str] = set()
    pattern = re.compile(r"\{\{[a-zA-Z0-9_]+\}\}")

    def collect_text(text: str) -> None:
        for match in pattern.findall(text or ""):
            found.add(match)

    for paragraph in document.paragraphs:
        collect_text(paragraph.text)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    collect_text(paragraph.text)
    for section in document.sections:
        for part in (section.header, section.footer):
            for paragraph in part.paragraphs:
                collect_text(paragraph.text)
            for table in part.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            collect_text(paragraph.text)

    return sorted(found)


def available_pdf_converter() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def convert_docx_to_pdf(docx_bytes: bytes) -> bytes | None:
    converter = available_pdf_converter()
    if not converter:
        return None

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "generated_cv.docx"
        pdf_path = temp_path / "generated_cv.pdf"
        source_path.write_bytes(docx_bytes)
        subprocess.run(
            [converter, "--headless", "--convert-to", "pdf", "--outdir", str(temp_path), str(source_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=90,
        )
        if not pdf_path.exists():
            return None
        return pdf_path.read_bytes()


def safe_filename(value: str, fallback: str = "surveyor_cv") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._-")
    return cleaned or fallback
