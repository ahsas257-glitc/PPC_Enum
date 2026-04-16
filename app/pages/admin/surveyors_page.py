import pandas as pd
import streamlit as st

from app.core.constants import GENDERS
from app.core.exceptions import UserFacingError
from app.core.permissions import ensure_role
from app.core.session import get_current_user
from app.design.components.cards import render_hero, render_panel_intro
from app.design.components.filters import apply_text_filter
from app.design.components.tables import render_table
from app.design.components import validation as vf
from app.repositories.province_repository import ProvinceRepository
from app.services.surveyor_service import SurveyorService

SURVEYOR_FORM_KEY = "surveyor_form"
SURVEYOR_NAME_KEY = "surveyor_form_name"
SURVEYOR_GENDER_KEY = "surveyor_form_gender"
SURVEYOR_FATHER_KEY = "surveyor_form_father"
SURVEYOR_TAZKIRA_KEY = "surveyor_form_tazkira"
SURVEYOR_EMAIL_KEY = "surveyor_form_email"
SURVEYOR_WHATSAPP_KEY = "surveyor_form_whatsapp"
SURVEYOR_PHONE_KEY = "surveyor_form_phone"
SURVEYOR_PERMANENT_PROVINCE_KEY = "surveyor_form_permanent_province"
SURVEYOR_CURRENT_PROVINCE_KEY = "surveyor_form_current_province"
SURVEYOR_CV_LINK_KEY = "surveyor_form_cv_link"
SURVEYOR_CV_FILE_KEY = "surveyor_form_cv_file"
SURVEYOR_TAZKIRA_IMAGE_KEY = "surveyor_form_tazkira_image"
SURVEYOR_TAZKIRA_PDF_KEY = "surveyor_form_tazkira_pdf"
SURVEYOR_TAZKIRA_WORD_KEY = "surveyor_form_tazkira_word"
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_SIZE_MB = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)


def _file_payload(file_obj, label: str):
    if not file_obj:
        return None, None, None
    if getattr(file_obj, "size", 0) > MAX_UPLOAD_SIZE_BYTES:
        raise UserFacingError(f"{label} must be {MAX_UPLOAD_SIZE_MB} MB or smaller.")
    return file_obj.getvalue(), file_obj.name, file_obj.type


def render_surveyors_page() -> None:
    ensure_role("super_admin", "admin", "manager")
    service = SurveyorService()

    render_hero(
        "Registry",
        kicker="Surveyors",
    )
    active_view = st.radio(
        "Surveyors view",
        ["New Surveyor", "Surveyor Data"],
        key="surveyors_active_view",
        horizontal=True,
        label_visibility="collapsed",
    )

    if active_view == "Surveyor Data":
        render_panel_intro("Surveyor List", eyebrow=None)
        rows = pd.DataFrame(service.list_surveyors(limit=500))
        if not rows.empty:
            rows = rows[
                [
                    "surveyor_code",
                    "surveyor_name",
                    "gender",
                    "email_address",
                    "phone_number",
                    "permanent_province_name",
                    "current_province_name",
                    "has_cv_file",
                    "has_tazkira_image",
                    "has_tazkira_pdf",
                    "has_tazkira_word",
                ]
            ]
            rows = apply_text_filter(rows, "Search surveyors")
        render_table(rows)
        return

    provinces = ProvinceRepository().list_all()
    province_map = {f"{item['province_name']} ({item['province_code']})": item["province_code"] for item in provinces}

    render_panel_intro("Create New Surveyor", eyebrow=None)
    province_options = list(province_map.keys()) if province_map else ["No provinces"]
    with st.form(SURVEYOR_FORM_KEY, clear_on_submit=False):
        vf.render_form_error_summary(SURVEYOR_FORM_KEY)
        left, right = st.columns(2)
        with left:
            surveyor_name = vf.text_input(SURVEYOR_FORM_KEY, SURVEYOR_NAME_KEY, "Surveyor name", required=True)
            gender = vf.selectbox(SURVEYOR_FORM_KEY, SURVEYOR_GENDER_KEY, "Gender", GENDERS, required=True)
            father_name = vf.text_input(SURVEYOR_FORM_KEY, SURVEYOR_FATHER_KEY, "Father name", required=True)
            tazkira_no = vf.text_input(SURVEYOR_FORM_KEY, SURVEYOR_TAZKIRA_KEY, "Tazkira number", required=True, placeholder="1234-5678-90123")
            email_address = vf.text_input(SURVEYOR_FORM_KEY, SURVEYOR_EMAIL_KEY, "Email", required=True)
            whatsapp_number = vf.text_input(SURVEYOR_FORM_KEY, SURVEYOR_WHATSAPP_KEY, "WhatsApp", required=True, placeholder="+93700123456")
            phone_number = vf.text_input(SURVEYOR_FORM_KEY, SURVEYOR_PHONE_KEY, "Phone number", required=True, placeholder="+93700123456")
        with right:
            permanent_label = vf.selectbox(
                SURVEYOR_FORM_KEY,
                SURVEYOR_PERMANENT_PROVINCE_KEY,
                "Permanent province",
                province_options,
                required=True,
            )
            current_label = vf.selectbox(SURVEYOR_FORM_KEY, SURVEYOR_CURRENT_PROVINCE_KEY, "Current province", province_options, required=True)
            cv_link = vf.text_input(SURVEYOR_FORM_KEY, SURVEYOR_CV_LINK_KEY, "CV link")
            cv_file = vf.file_uploader(SURVEYOR_FORM_KEY, SURVEYOR_CV_FILE_KEY, "CV file", type=["pdf", "doc", "docx"])
            tazkira_image = vf.file_uploader(
                SURVEYOR_FORM_KEY,
                SURVEYOR_TAZKIRA_IMAGE_KEY,
                "Tazkira image",
                type=["png", "jpg", "jpeg"],
            )
            tazkira_pdf = vf.file_uploader(SURVEYOR_FORM_KEY, SURVEYOR_TAZKIRA_PDF_KEY, "Tazkira PDF", type=["pdf"])
            tazkira_word = vf.file_uploader(
                SURVEYOR_FORM_KEY,
                SURVEYOR_TAZKIRA_WORD_KEY,
                "Tazkira Word",
                type=["doc", "docx"],
            )
            st.caption(f"Each uploaded file can be up to {MAX_UPLOAD_SIZE_MB} MB.")
        submitted = st.form_submit_button("Create surveyor", width="stretch")

    if submitted:
        errors = {}
        if not province_map:
            errors[SURVEYOR_PERMANENT_PROVINCE_KEY] = "Add province records before creating surveyors."
            errors[SURVEYOR_CURRENT_PROVINCE_KEY] = "Add province records before creating surveyors."
        if errors:
            errors[vf.FORM_MESSAGE_KEY] = "Please fix the highlighted surveyor fields."
            vf.stop_with_form_errors(SURVEYOR_FORM_KEY, errors)
        try:
            cv_bytes, cv_name, cv_mime = _file_payload(cv_file, "CV file")
            image_bytes, image_name, image_mime = _file_payload(tazkira_image, "Tazkira image")
            pdf_bytes, pdf_name, pdf_mime = _file_payload(tazkira_pdf, "Tazkira PDF")
            word_bytes, word_name, word_mime = _file_payload(tazkira_word, "Tazkira Word")
        except UserFacingError as exc:
            vf.stop_with_form_errors(
                SURVEYOR_FORM_KEY,
                vf.field_errors_from_message(
                    str(exc),
                    {
                        SURVEYOR_CV_FILE_KEY: ("cv file",),
                        SURVEYOR_TAZKIRA_IMAGE_KEY: ("tazkira image",),
                        SURVEYOR_TAZKIRA_PDF_KEY: ("tazkira pdf",),
                        SURVEYOR_TAZKIRA_WORD_KEY: ("tazkira word",),
                    },
                ),
            )
        payload = {
            "surveyor_name": surveyor_name.strip(),
            "gender": gender,
            "father_name": father_name.strip(),
            "tazkira_no": tazkira_no.strip(),
            "email_address": email_address.strip(),
            "whatsapp_number": whatsapp_number.strip(),
            "phone_number": phone_number.strip(),
            "permanent_province_code": province_map[permanent_label],
            "current_province_code": province_map[current_label],
            "cv_link": cv_link.strip() or None,
            "cv_file": cv_bytes,
            "cv_file_name": cv_name,
            "cv_mime": cv_mime,
            "tazkira_image": image_bytes,
            "tazkira_image_name": image_name,
            "tazkira_image_mime": image_mime,
            "tazkira_pdf": pdf_bytes,
            "tazkira_pdf_name": pdf_name,
            "tazkira_pdf_mime": pdf_mime,
            "tazkira_word": word_bytes,
            "tazkira_word_name": word_name,
            "tazkira_word_mime": word_mime,
        }
        errors = vf.required_errors(
            {
                SURVEYOR_NAME_KEY: (payload["surveyor_name"], "Enter the surveyor name."),
                SURVEYOR_FATHER_KEY: (payload["father_name"], "Enter the father's name."),
                SURVEYOR_TAZKIRA_KEY: (payload["tazkira_no"], "Enter the tazkira number."),
                SURVEYOR_EMAIL_KEY: (payload["email_address"], "Enter the email address."),
                SURVEYOR_WHATSAPP_KEY: (payload["whatsapp_number"], "Enter the WhatsApp number."),
                SURVEYOR_PHONE_KEY: (payload["phone_number"], "Enter the phone number."),
            }
        )
        errors.update(vf.email_errors({SURVEYOR_EMAIL_KEY: (email_address, "Enter a valid email address, for example name@example.com.")}))
        errors.update(
            vf.tazkira_errors(
                {
                    SURVEYOR_TAZKIRA_KEY: (
                        tazkira_no,
                        "Enter a valid tazkira number in this format: 1234-5678-90123.",
                    )
                }
            )
        )
        errors.update(
            vf.phone_errors(
                {
                    SURVEYOR_WHATSAPP_KEY: (
                        whatsapp_number,
                        "Enter a valid WhatsApp number in international format, for example +93700123456.",
                    ),
                    SURVEYOR_PHONE_KEY: (
                        phone_number,
                        "Enter a valid phone number in international format, for example +93700123456.",
                    ),
                }
            )
        )
        if errors:
            errors[vf.FORM_MESSAGE_KEY] = "Please fix the highlighted surveyor fields."
            vf.stop_with_form_errors(SURVEYOR_FORM_KEY, errors)
        try:
            created = service.create_surveyor(get_current_user(), payload)
        except Exception as exc:
            message = vf.user_friendly_error_message(
                exc,
                "We could not create this surveyor right now. Check the highlighted information and try again.",
            )
            vf.stop_with_form_errors(
                SURVEYOR_FORM_KEY,
                vf.field_errors_from_message(
                    message,
                    {
                        SURVEYOR_TAZKIRA_KEY: ("tazkira",),
                        SURVEYOR_EMAIL_KEY: ("email",),
                        SURVEYOR_WHATSAPP_KEY: ("whatsapp",),
                        SURVEYOR_PHONE_KEY: ("phone",),
                        SURVEYOR_PERMANENT_PROVINCE_KEY: ("province",),
                        SURVEYOR_CURRENT_PROVINCE_KEY: ("province",),
                    },
                ),
            )
        vf.clear_form_errors(SURVEYOR_FORM_KEY)
        st.success(f"Surveyor created with code {created['surveyor_code']}.")
        st.rerun()
