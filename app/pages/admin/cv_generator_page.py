from __future__ import annotations

import hashlib
import subprocess

import pandas as pd
import streamlit as st

from app.core.permissions import ensure_role
from app.design.components.cards import render_hero, render_panel_intro
from app.design.components.tables import render_table
from app.services.cv_template_service import (
    MAX_TEMPLATE_SIZE_BYTES,
    MAX_TEMPLATE_SIZE_MB,
    PLACEHOLDER_FIELDS,
    WORD_MIME,
    available_pdf_converter,
    build_replacement_map,
    convert_docx_to_pdf,
    find_unreplaced_placeholders,
    render_docx_template,
    safe_filename,
)
from app.services.surveyor_service import SurveyorService

OUTPUT_STATE_KEY = "cv_generator_output"
PDF_STATE_KEY = "cv_generator_pdf_output"


def _surveyor_label(row: dict) -> str:
    code = str(row.get("surveyor_code") or "").strip()
    name = str(row.get("surveyor_name") or "").strip()
    if code and name:
        return f"{name} ({code})"
    return name or code or f"Surveyor #{row.get('surveyor_id')}"


def _template_digest(template_bytes: bytes) -> str:
    return hashlib.sha256(template_bytes).hexdigest()


def _output_file_base(replacements: dict[str, str]) -> str:
    name_part = safe_filename(replacements.get("surveyor_name", ""))
    code_part = safe_filename(replacements.get("surveyor_code", ""))
    if code_part and name_part:
        return f"cv_{code_part}_{name_part}"
    return f"cv_{code_part or name_part or 'surveyor'}"


def _preview_frame(replacements: dict[str, str]) -> pd.DataFrame:
    fields = [
        ("Surveyor", replacements.get("surveyor_name", "")),
        ("Code", replacements.get("surveyor_code", "")),
        ("Father", replacements.get("father_name", "")),
        ("Tazkira", replacements.get("tazkira_no", "")),
        ("Phone", replacements.get("phone_number", "")),
        ("WhatsApp", replacements.get("whatsapp_number", "")),
        ("Current province", replacements.get("current_province_name", "")),
        ("Default payout", replacements.get("default_payout_value", "")),
        ("Projects", replacements.get("project_names", "")),
    ]
    return pd.DataFrame([{"Field": label, "Value": value or ""} for label, value in fields])


def _placeholder_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [{"Placeholder": f"{{{{{field}}}}}", "Meaning": description} for field, description in PLACEHOLDER_FIELDS]
    )


def _read_template_file(uploaded_file) -> bytes | None:
    if not uploaded_file:
        return None
    if getattr(uploaded_file, "size", 0) > MAX_TEMPLATE_SIZE_BYTES:
        st.warning(f"Template must be {MAX_TEMPLATE_SIZE_MB} MB or smaller.")
        return None
    return uploaded_file.getvalue()


def _render_placeholder_help() -> None:
    with st.expander("Template placeholders", expanded=False):
        st.caption("Use placeholders when you want exact control. Standard Form H tables can also be filled automatically.")
        render_table(_placeholder_frame(), max_visible_rows=12, row_height=30)
        st.code("{{surveyor_name}}\n{{phone_number}}\n{{assignments}}\n{{bank_accounts}}", language="text")


def _render_form_h_extra_fields() -> dict[str, str]:
    with st.expander("Optional Form H fields", expanded=False):
        st.caption("These fields are used only when the uploaded template has Form H labels and the value is not stored for the surveyor.")
        left, right = st.columns(2)
        with left:
            proposer_name = st.text_input("Name of proposer", key="cv_generator_proposer_name")
            rfp_reference = st.text_input("RFP reference", key="cv_generator_rfp_reference")
            position_tor = st.text_input("Position as per ToR", key="cv_generator_position_tor")
            nationality = st.text_input("Nationality", key="cv_generator_nationality")
        with right:
            date_of_birth = st.text_input("Date of birth", key="cv_generator_date_of_birth", placeholder="YYYY-MM-DD")
            language_proficiency = st.text_input("Language proficiency", key="cv_generator_language")
            education_qualifications = st.text_area("Education / Qualifications", key="cv_generator_education", height=84)
            professional_certifications = st.text_area("Professional Certifications", key="cv_generator_certifications", height=84)
        references = st.text_area("References", key="cv_generator_references", height=84)
    return {
        "proposer_name": proposer_name.strip(),
        "rfp_reference": rfp_reference.strip(),
        "position_tor": position_tor.strip(),
        "nationality": nationality.strip(),
        "date_of_birth": date_of_birth.strip(),
        "language_proficiency": language_proficiency.strip(),
        "education_qualifications": education_qualifications.strip(),
        "professional_certifications": professional_certifications.strip(),
        "references": references.strip(),
    }


def _render_ready_output(output: dict) -> None:
    st.success("CV is ready.")
    render_table(output["preview"], max_visible_rows=9, row_height=32)

    if output.get("missing_tokens"):
        st.warning(
            "These placeholders stayed in the document because they are not recognized: "
            + ", ".join(output["missing_tokens"])
        )

    left, right = st.columns(2)
    with left:
        st.download_button(
            "Download Word",
            data=output["docx_bytes"],
            file_name=f"{output['file_base']}.docx",
            mime=WORD_MIME,
            key="cv_generator_word_download",
            width="stretch",
        )

    with right:
        if not available_pdf_converter():
            st.info("PDF export needs LibreOffice installed on this server. Word export is ready now.")
            return

        if st.button("Prepare PDF", key="cv_generator_prepare_pdf", width="stretch"):
            try:
                with st.spinner("Preparing PDF..."):
                    pdf_bytes = convert_docx_to_pdf(output["docx_bytes"])
            except (subprocess.SubprocessError, OSError, TimeoutError) as exc:
                st.warning(f"PDF could not be prepared: {exc}")
                return
            if not pdf_bytes:
                st.warning("PDF could not be prepared. Download the Word file and export it from Word.")
                return
            st.session_state[PDF_STATE_KEY] = {
                "digest": output["digest"],
                "surveyor_id": output["surveyor_id"],
                "file_base": output["file_base"],
                "pdf_bytes": pdf_bytes,
            }

        pdf_output = st.session_state.get(PDF_STATE_KEY)
        if (
            pdf_output
            and pdf_output.get("digest") == output.get("digest")
            and pdf_output.get("surveyor_id") == output.get("surveyor_id")
        ):
            st.download_button(
                "Download PDF",
                data=pdf_output["pdf_bytes"],
                file_name=f"{pdf_output['file_base']}.pdf",
                mime="application/pdf",
                key="cv_generator_pdf_download",
                width="stretch",
            )


def render_cv_generator_page() -> None:
    ensure_role("super_admin", "admin", "manager")
    service = SurveyorService()

    render_hero(
        "CV Generator",
        "Upload a Word template, choose a surveyor, and export the filled CV.",
        kicker="Surveyors",
    )
    render_panel_intro("Generate Surveyor CV", eyebrow=None)

    surveyors = service.list_lookup(limit=1000)
    if not surveyors:
        st.info("No surveyors found yet. Add a surveyor first, then return to this page.")
        _render_placeholder_help()
        return

    surveyor_options = {_surveyor_label(row): row for row in surveyors}
    left, right = st.columns([0.95, 1.05], gap="large")
    with left:
        selected_label = st.selectbox("Surveyor", list(surveyor_options.keys()), key="cv_generator_surveyor")
        uploaded_template = st.file_uploader(
            "Word template (.docx)",
            type=["docx"],
            key="cv_generator_template",
            help="Use placeholders like {{surveyor_name}} inside the Word file.",
        )
        smart_fill = st.checkbox(
            "Auto-fill standard Form H tables",
            value=True,
            key="cv_generator_smart_fill",
            help="When the template has Form H labels, known table fields are filled even without placeholders.",
        )
        st.caption(f"Template limit: {MAX_TEMPLATE_SIZE_MB} MB. Old .doc files should be saved as .docx first.")
        generate = st.button("Generate formatted CV", type="primary", width="stretch")

    with right:
        _render_placeholder_help()
        extra_replacements = _render_form_h_extra_fields()

    template_bytes = _read_template_file(uploaded_template)
    selected_row = surveyor_options[selected_label]
    selected_surveyor_id = int(selected_row["surveyor_id"])

    if generate:
        if not template_bytes:
            st.warning("Upload a .docx CV template first.")
            return

        context = service.get_cv_context(selected_surveyor_id)
        if not context:
            st.warning("This surveyor could not be found. Refresh the page and try again.")
            return

        replacements = build_replacement_map(
            context["profile"],
            context.get("bank_accounts", []),
            context.get("assignments", []),
        )
        replacements.update({key: value for key, value in extra_replacements.items() if value})
        try:
            docx_bytes = render_docx_template(
                template_bytes,
                replacements,
                assignments=context.get("assignments", []),
                smart_fill=smart_fill,
            )
            missing_tokens = find_unreplaced_placeholders(docx_bytes)
        except Exception as exc:
            st.warning(f"The template could not be processed. Make sure it is a valid .docx file. Details: {exc}")
            return

        digest = _template_digest(template_bytes)
        output = {
            "digest": digest,
            "surveyor_id": selected_surveyor_id,
            "file_base": _output_file_base(replacements),
            "docx_bytes": docx_bytes,
            "preview": _preview_frame(replacements),
            "missing_tokens": missing_tokens,
        }
        st.session_state[OUTPUT_STATE_KEY] = output
        st.session_state.pop(PDF_STATE_KEY, None)

    output = st.session_state.get(OUTPUT_STATE_KEY)
    if output and output.get("surveyor_id") == selected_surveyor_id:
        _render_ready_output(output)
