from __future__ import annotations

import base64
from functools import lru_cache

import streamlit as st

from app.design.theme import CSS_DIR, CSS_FILE_ORDER, LOGO_FILE


@lru_cache(maxsize=1)
def _logo_data_uri() -> str:
    if not LOGO_FILE.exists():
        return ""
    encoded = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@lru_cache(maxsize=1)
def _load_css_bundle() -> str:
    return "\n".join(
        (CSS_DIR / name).read_text(encoding="utf-8")
        for name in CSS_FILE_ORDER
        if (CSS_DIR / name).exists()
    )


def inject_base_styles(*, authenticated: bool = False) -> None:
    logo_uri = _logo_data_uri()
    logo_rule = f'--logo-url: url("{logo_uri}");' if logo_uri else "--logo-url: none;"

    if authenticated:
        app_bg = """
            radial-gradient(circle at 10% 14%, rgba(108, 211, 255, 0.16), transparent 0 24%),
            radial-gradient(circle at 84% 12%, rgba(104, 154, 255, 0.14), transparent 0 22%),
            radial-gradient(circle at 72% 78%, rgba(111, 236, 224, 0.10), transparent 0 24%),
            linear-gradient(145deg, #02060d 0%, #07111b 30%, #0a1420 62%, #040811 100%)
        """
        app_glow = """
            radial-gradient(circle at 16% 18%, rgba(121, 220, 255, 0.18), transparent 22%),
            radial-gradient(circle at 78% 20%, rgba(111, 170, 255, 0.14), transparent 20%),
            radial-gradient(circle at 66% 82%, rgba(135, 241, 227, 0.08), transparent 22%)
        """
        logo_opacity = "0.055"
        grid_opacity = "0.08"
    else:
        app_bg = """
            radial-gradient(circle at 12% 14%, rgba(108, 211, 255, 0.08), transparent 0 18%),
            radial-gradient(circle at 84% 12%, rgba(104, 154, 255, 0.07), transparent 0 16%),
            linear-gradient(145deg, #030711 0%, #08111b 44%, #09131d 100%)
        """
        app_glow = """
            radial-gradient(circle at 18% 18%, rgba(121, 220, 255, 0.09), transparent 20%),
            radial-gradient(circle at 76% 18%, rgba(111, 170, 255, 0.08), transparent 18%)
        """
        logo_opacity = "0"
        grid_opacity = "0.05"

    public_overrides = (
        """
        /* Public login shell: compact, quiet, and focused. */
        .block-container {
            max-width: min(980px, calc(100vw - 2.2rem)) !important;
            margin-top: clamp(2.8rem, 5vh, 4rem) !important;
            margin-bottom: clamp(1.4rem, 3vh, 2.4rem) !important;
            padding: 0.82rem 0.88rem !important;
            font-size: 0.88rem !important;
        }

        .block-container::before,
        .block-container::after {
            inset: 0.18rem !important;
            border-radius: 18px !important;
        }

        .block-container [data-testid="stHorizontalBlock"] {
            align-items: center !important;
            gap: 1rem !important;
        }

        .glass-hero {
            min-height: 88px !important;
            margin-bottom: 0 !important;
            padding: 0.82rem 0.9rem !important;
            border-radius: 16px !important;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,0.04),
                0 12px 28px rgba(1, 8, 18, 0.14) !important;
        }

        .glass-hero-grid {
            grid-template-columns: 1fr !important;
        }

        .glass-hero h1 {
            font-size: clamp(1.42rem, 2.1vw, 1.9rem) !important;
            line-height: 1.05 !important;
        }

        .glass-hero p {
            max-width: 34rem !important;
            margin-top: 0.46rem !important;
            font-size: 0.86rem !important;
            line-height: 1.54 !important;
            color: rgba(220, 236, 250, 0.72) !important;
        }

        .glass-hero-orbit,
        .glass-hero-backdrop,
        .panel-orb,
        .stat-band {
            display: none !important;
        }

        .panel-intro {
            margin-bottom: 0.62rem !important;
            padding: 0.78rem 0.9rem !important;
            border-radius: 16px !important;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,0.04),
                0 12px 28px rgba(1, 8, 18, 0.14) !important;
        }

        .panel-intro-row {
            gap: 0.72rem !important;
        }

        .panel-intro h3 {
            font-size: 1.08rem !important;
            line-height: 1.12 !important;
        }

        .glass-panel-meta {
            margin-top: 0.34rem !important;
            font-size: 0.8rem !important;
            line-height: 1.45 !important;
            color: rgba(220, 236, 250, 0.68) !important;
        }

        [data-baseweb="tab-list"] {
            margin-bottom: 0.72rem !important;
            padding: 0.24rem !important;
            border-radius: 12px !important;
            gap: 0.24rem !important;
        }

        [data-baseweb="tab"] {
            min-height: 36px !important;
            padding: 0.52rem 0.78rem !important;
            border-radius: 8px !important;
            font-size: 0.78rem !important;
        }

        div[data-testid="stForm"] {
            margin-top: 0.58rem !important;
            padding: 0.82rem 0.86rem 0.78rem !important;
            border-radius: 16px !important;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,0.035),
                0 12px 30px rgba(1, 8, 18, 0.16) !important;
        }

        div[data-testid="stForm"] > div:first-child,
        div[data-testid="stForm"] [data-testid="stVerticalBlock"],
        div[data-testid="stForm"] [data-testid="column"] > div {
            gap: 0.68rem !important;
        }

        label[data-testid="stWidgetLabel"] p,
        .stCaption p,
        [data-testid="stCaptionContainer"] p {
            font-size: 0.76rem !important;
            line-height: 1.32 !important;
        }

        .block-container [data-testid="stTextInput"] [data-baseweb="input"],
        .block-container [data-testid="stTextInput"] [data-baseweb="base-input"],
        .block-container [data-testid="stNumberInput"] [data-baseweb="input"],
        .block-container [data-testid="stDateInput"] [data-baseweb="input"],
        .block-container [data-testid="stSelectbox"] [data-baseweb="select"],
        .block-container [data-testid="stMultiSelect"] [data-baseweb="select"] {
            min-height: 42px !important;
            border-radius: 10px !important;
        }

        .block-container [data-testid="stTextInput"] input,
        .block-container [data-testid="stSelectbox"] input,
        .block-container [data-baseweb="select"] div,
        .block-container [data-baseweb="select"] span {
            min-height: 40px !important;
            font-size: 0.82rem !important;
        }

        button[title="Show password text"],
        button[title="Hide password text"],
        button[aria-label="Show password text"],
        button[aria-label="Hide password text"] {
            min-width: 30px !important;
            width: 30px !important;
            height: 30px !important;
        }

        div[data-testid="stFormSubmitButton"] {
            margin-top: 0.72rem !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFormSubmitButton"] button {
            min-height: 40px !important;
            padding: 0.58rem 0.82rem !important;
            border-radius: 10px !important;
            font-size: 0.82rem !important;
        }

        @media (max-width: 767.98px) {
            .block-container {
                max-width: calc(100vw - 0.8rem) !important;
                margin-top: 3.1rem !important;
                padding: 0.68rem !important;
            }

            .block-container [data-testid="stHorizontalBlock"] {
                gap: 0.76rem !important;
            }

            .glass-hero,
            .panel-intro,
            div[data-testid="stForm"] {
                border-radius: 14px !important;
            }
        }
        """
        if not authenticated
        else ""
    )

    st.markdown(
        f"""
        <style>
        :root {{
            color-scheme: dark;

            /* Typography */
            --font-body: Inter, "Segoe UI Variable", "Segoe UI", "Aptos", sans-serif;
            --font-display: "Sora", "Segoe UI Variable Display", Inter, "Aptos", sans-serif;
            --font-mono: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;

            /* App backgrounds */
            --app-bg: {app_bg};
            --app-glow: {app_glow};
            --app-sidebar-bg:
                linear-gradient(180deg, rgba(7, 14, 24, 0.94), rgba(4, 9, 16, 0.98));
            --app-grid:
                linear-gradient(rgba(255,255,255,0.028) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.028) 1px, transparent 1px);

            /* Surface system */
            --surface: rgba(15, 24, 38, 0.62);
            --surface-soft: rgba(13, 21, 34, 0.44);
            --surface-elevated: rgba(16, 26, 40, 0.76);
            --surface-strong: rgba(10, 17, 28, 0.88);
            --surface-overlay: rgba(7, 14, 24, 0.74);
            --surface-highlight: rgba(255, 255, 255, 0.08);

            /* Borders */
            --stroke: rgba(151, 192, 230, 0.14);
            --stroke-soft: rgba(151, 192, 230, 0.08);
            --stroke-strong: rgba(108, 201, 255, 0.34);
            --stroke-focus: rgba(104, 196, 255, 0.54);

            /* Text */
            --text: #f5fbff;
            --text-soft: rgba(220, 236, 250, 0.82);
            --text-muted: rgba(181, 204, 224, 0.60);
            --text-faint: rgba(181, 204, 224, 0.42);

            /* Accent system */
            --accent: #79dcff;
            --accent-strong: #6aa8ff;
            --accent-secondary: #87f1e3;
            --accent-warm: #b4cfff;
            --accent-danger: #ff7d92;
            --accent-success: #6ee7b7;
            --accent-warning: #f7c873;

            /* Shadows */
            --shadow-xs: 0 2px 10px rgba(1, 8, 18, 0.10);
            --shadow-sm: 0 8px 22px rgba(1, 8, 18, 0.16);
            --shadow-md: 0 18px 44px rgba(1, 8, 18, 0.24);
            --shadow-lg: 0 28px 72px rgba(1, 7, 16, 0.34);
            --shadow-xl: 0 36px 110px rgba(1, 7, 16, 0.46);
            --focus-ring: 0 0 0 4px rgba(104, 196, 255, 0.16);

            /* Radius */
            --radius-xs: 10px;
            --radius-sm: 14px;
            --radius-md: 18px;
            --radius-lg: 24px;
            --radius-xl: 30px;
            --radius-pill: 999px;

            /* Motion */
            --ease-standard: cubic-bezier(0.22, 1, 0.36, 1);
            --ease-soft: cubic-bezier(0.16, 1, 0.3, 1);
            --duration-fast: 160ms;
            --duration-base: 220ms;
            --duration-slow: 420ms;

            /* Brand layer */
            {logo_rule}
            --logo-opacity: {logo_opacity};
            --logo-size: clamp(150px, 16vw, 240px);
            --logo-position: right 1.4rem bottom 1.2rem;
            --grid-size: 34px 34px;
            --grid-opacity: {grid_opacity};

            /* Layout */
            --content-max-width: 1440px;
        }}

        html {{
            color-scheme: dark;
            scroll-behavior: smooth;
        }}

        body,
        [class*="css"] {{
            font-family: var(--font-body);
            color: var(--text);
            background: var(--app-bg);
        }}

        body {{
            overflow-x: hidden;
            text-rendering: optimizeLegibility;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}

        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main {{
            min-height: 100vh;
            position: relative;
            isolation: isolate;
            background: var(--app-bg);
        }}

        /* Ambient layers */
        .stApp::before,
        .stApp::after,
        [data-testid="stAppViewContainer"]::before {{
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
        }}

        .stApp::before {{
            background: var(--app-glow);
            filter: blur(24px) saturate(118%);
            opacity: 0.9;
            transform: translateZ(0);
        }}

        [data-testid="stAppViewContainer"]::before {{
            background-image: var(--app-grid);
            background-size: var(--grid-size);
            mask-image: radial-gradient(circle at center, black 34%, transparent 100%);
            -webkit-mask-image: radial-gradient(circle at center, black 34%, transparent 100%);
            opacity: var(--grid-opacity);
        }}

        .stApp::after {{
            background-image: var(--logo-url);
            background-repeat: no-repeat;
            background-position: var(--logo-position);
            background-size: var(--logo-size);
            opacity: var(--logo-opacity);
            filter:
                brightness(1.18)
                saturate(1.02)
                contrast(1.02)
                drop-shadow(0 20px 42px rgba(64, 171, 255, 0.12));
            animation: appLogoFloat 18s var(--ease-soft) infinite alternate;
            transform-origin: center;
        }}

        [data-testid="stSidebar"] .stApp::after,
        [data-testid="stSidebar"]::after {{
            display: none !important;
        }}

        /* Main header */
        [data-testid="stHeader"] {{
            background: linear-gradient(
                180deg,
                rgba(4, 10, 18, 0.86),
                rgba(4, 10, 18, 0.42)
            ) !important;
            border-bottom: 1px solid rgba(151, 192, 230, 0.08);
            backdrop-filter: blur(18px) saturate(150%);
            -webkit-backdrop-filter: blur(18px) saturate(150%);
        }}

        /* Hide Streamlit chrome */
        #MainMenu,
        footer,
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {{
            display: none !important;
        }}

        /* Top bar controls */
        [data-testid="stHeader"] button,
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapseButton"],
        button[title="Open sidebar"],
        button[title="Close sidebar"] {{
            border-radius: var(--radius-pill) !important;
            border: 1px solid var(--stroke) !important;
            background: rgba(10, 18, 29, 0.78) !important;
            color: var(--text) !important;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,0.06),
                0 10px 28px rgba(1, 7, 16, 0.22) !important;
            transition:
                background var(--duration-fast) var(--ease-standard),
                border-color var(--duration-fast) var(--ease-standard),
                box-shadow var(--duration-fast) var(--ease-standard),
                transform var(--duration-fast) var(--ease-standard) !important;
        }}

        [data-testid="stHeader"] button:hover,
        [data-testid="collapsedControl"]:hover,
        [data-testid="stSidebarCollapseButton"]:hover,
        button[title="Open sidebar"]:hover,
        button[title="Close sidebar"]:hover {{
            border-color: rgba(104, 196, 255, 0.26) !important;
            background: rgba(13, 23, 37, 0.92) !important;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,0.08),
                0 14px 32px rgba(1, 7, 16, 0.26) !important;
            transform: translateY(-1px);
        }}

        [data-testid="stHeader"] button:focus-visible,
        [data-testid="collapsedControl"]:focus-visible,
        [data-testid="stSidebarCollapseButton"]:focus-visible,
        button[title="Open sidebar"]:focus-visible,
        button[title="Close sidebar"]:focus-visible {{
            outline: none !important;
            box-shadow: var(--focus-ring) !important;
            border-color: var(--stroke-focus) !important;
        }}

        /* Sidebar shell */
        [data-testid="stSidebar"] {{
            background: var(--app-sidebar-bg) !important;
            overflow: hidden !important;
            border-right: 1px solid rgba(151, 192, 230, 0.08) !important;
            box-shadow:
                inset -1px 0 0 rgba(255,255,255,0.02),
                10px 0 30px rgba(1, 7, 16, 0.12) !important;
        }}

        [data-testid="stSidebar"] > div:first-child {{
            background:
                radial-gradient(circle at top left, rgba(121, 220, 255, 0.12), transparent 28%),
                linear-gradient(180deg, rgba(7, 14, 24, 0.96), rgba(4, 9, 16, 0.98)) !important;
            backdrop-filter: blur(22px) saturate(150%);
            -webkit-backdrop-filter: blur(22px) saturate(150%);
        }}

        [data-testid="stSidebar"] * {{
            color: var(--text) !important;
        }}

        /* Better typography defaults */
        h1, h2, h3, h4, h5, h6 {{
            font-family: var(--font-display);
            color: var(--text);
            letter-spacing: -0.02em;
            line-height: 1.08;
            text-wrap: balance;
        }}

        p, li, label, span {{
            text-wrap: pretty;
        }}

        a {{
            color: var(--accent);
            text-decoration: none;
            transition: color var(--duration-fast) var(--ease-standard);
        }}

        a:hover {{
            color: #a9e8ff;
        }}

        /* Scrollbar */
        * {{
            scrollbar-width: thin;
            scrollbar-color: rgba(125, 190, 235, 0.28) transparent;
        }}

        *::-webkit-scrollbar {{
            width: 10px;
            height: 10px;
        }}

        *::-webkit-scrollbar-track {{
            background: transparent;
        }}

        *::-webkit-scrollbar-thumb {{
            background: linear-gradient(
                180deg,
                rgba(110, 176, 225, 0.32),
                rgba(86, 144, 204, 0.22)
            );
            border: 2px solid transparent;
            background-clip: padding-box;
            border-radius: 999px;
        }}

        *::-webkit-scrollbar-thumb:hover {{
            background: linear-gradient(
                180deg,
                rgba(128, 196, 244, 0.42),
                rgba(95, 156, 220, 0.30)
            );
            border: 2px solid transparent;
            background-clip: padding-box;
        }}

        @keyframes appLogoFloat {{
            from {{
                transform: translate3d(0, 0, 0) scale(1);
            }}
            to {{
                transform: translate3d(0, -6px, 0) scale(1.015);
            }}
        }}

        @media (prefers-reduced-motion: reduce) {{
            html {{
                scroll-behavior: auto;
            }}

            *,
            *::before,
            *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }}
        }}

        @media (max-width: 1200px) {{
            :root {{
                --logo-opacity: 0 !important;
            }}
        }}

        @media (max-width: 900px) {{
            :root {{
                --logo-opacity: 0 !important;
                --grid-opacity: 0.035;
            }}
        }}

        @media (max-width: 640px) {{
            :root {{
                --radius-lg: 20px;
                --radius-xl: 24px;
                --logo-position: right 0.85rem bottom 0.85rem;
            }}
        }}

        {_load_css_bundle()}

        /* Performance mode: keep the UI sharp without GPU-heavy paint work. */
        *,
        *::before,
        *::after {{
            will-change: auto !important;
        }}

        .stApp::before,
        .stApp::after,
        [data-testid="stAppViewContainer"]::before,
        [class*="orb"],
        [class*="halo"],
        [class*="ring"] {{
            animation: none !important;
            filter: none !important;
        }}

        [data-testid="stHeader"],
        [data-testid="stSidebar"] > div:first-child,
        [data-testid="stAlert"],
        [class*="card"],
        [class*="panel"],
        [class*="metric"],
        [class*="hero"],
        [class*="table"],
        [class*="form"] {{
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
        }}

        [data-testid="stHeader"] button,
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapseButton"],
        button[title="Open sidebar"],
        button[title="Close sidebar"] {{
            transition-duration: 80ms !important;
        }}

        {public_overrides}
        </style>
        """,
        unsafe_allow_html=True,
    )
    
