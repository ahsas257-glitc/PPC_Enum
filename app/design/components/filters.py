import pandas as pd
import streamlit as st


def apply_text_filter(frame: pd.DataFrame, label: str = "Quick search") -> pd.DataFrame:
    query = st.text_input(label, placeholder="Type to filter...").strip()
    if frame.empty or len(query) < 2:
        return frame

    mask = pd.Series(False, index=frame.index)
    for column in frame.columns:
        mask |= frame[column].astype("string").str.contains(query, case=False, na=False, regex=False)
        if bool(mask.all()):
            break
    return frame[mask]
