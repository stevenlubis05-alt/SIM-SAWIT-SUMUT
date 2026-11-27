from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st

# ============================================================
# SIM-SAWIT SUMUT | Dashboard data perkebunan kelapa sawit
# Database pusat Neon: sawit_kecamatan_pusat, sawit_kabupaten,
# dan harga_tbs_kabupaten.
# ============================================================

st.set_page_config(
    page_title="SIM-SAWIT SUMUT | Dashboard",
    page_icon="🌴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Tampilan / CSS
# -----------------------------
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@500;600;700;800&display=swap');
      html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
      .stApp { background: #f3f7f4; }
      [data-testid="stHeader"] { background: rgba(243,247,244,0.88); }
      [data-testid="stSidebar"] { background: linear-gradient(180deg,#102f2a 0%,#16483d 100%); }
      [data-testid="stSidebar"] * { color: #eefbf4 !important; }
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #d6ebe1 !important; }
      [data-testid="stSidebar"] .stRadio label { padding: 7px 4px; }
      .hero {
        background: linear-gradient(115deg,#103c32 0%,#167452 55%,#39a66e 100%);
        padding: 28px 32px; border-radius: 22px; color: white;
        box-shadow: 0 12px 30px rgba(18,75,55,.16); margin-bottom: 18px;
      }
      .hero h1 { font-family: 'Manrope',sans-serif; font-size: 31px; line-height: 1.15; margin: 0 0 8px 0; color: white; }
      .hero p { color: #e3f6ec; font-size: 14px; margin: 0; max-width: 850px; }
      .eyebrow { text-transform: uppercase; letter-spacing: 1.8px; font-size: 10px; font-weight: 800; color: #c0f0d4; margin-bottom: 9px; }
      .section-title { font-family:'Manrope',sans-serif; color:#153e32; font-weight:800; font-size:20px; margin: 7px 0 3px 0; }
      .section-sub { color:#6b8177; font-size:12px; margin-bottom:13px; }
      .metric-card { background:white; border:1px solid #e2ece5; border-radius:16px; padding:17px 18px; min-height:114px; box-shadow:0 4px 13px rgba(21,62,50,.035); }
      .metric-label { color:#71877c; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.65px; }
      .metric-value { color:#173f33; font-family:'Manrope',sans-serif; font-size:25px; font-weight:800; margin-top:8px; line-height:1.15; }
      .metric-note { color:#8a9b92; font-size:10px; margin-top:6px; }
      .info-card { background:#ffffff; border:1px solid #e1ebe4; padding:16px 18px; border-radius:15px; }
      .insight-card { background:linear-gradient(135deg,#e8f6ee,#f8fcf9); border:1px solid #d6ecdf; padding:17px 18px; border-radius:15px; color:#234a3c; }
      .warn-card { background:#fff7e7; border:1px solid #f3dfb4; padding:14px 16px; border-radius:13px; color:#76541a; }
      .soft-card { background:#f9fcfa; border:1px solid #e3eee7; padding:13px 15px; border-radius:13px; }
      .tag { display:inline-block; border-radius:99px; padding:4px 9px; font-size:10px; font-weight:700; margin-right:5px; }
      .tag-green { background:#dff3e7; color:#17613f; }
      .tag-amber { background:#fff0ce; color:#855b0c; }
      .tag-blue { background:#e1effa; color:#245c87; }
      div[data-testid="stDataFrame"] { border:1px solid #e2ebe5; border-radius:12px; overflow:hidden; }
      div[data-testid="stPlotlyChart"] { background:white; border:1px solid #e4ede7; border-radius:15px; padding:8px 8px 0 8px; }
      .small-muted { color:#7c8e84; font-size:11px; }
      footer { visibility:hidden; }
      #MainMenu { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Data referensi dari dokumen sumber
# -----------------------------

def load_csv(name: str) -> pd.DataFrame:
    path = os.path.join(os.path.dirname(__file__), "data", name)
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def get_connection_string() -> str | None:
    """Membaca connection string Neon dari Streamlit secrets atau environment."""
    candidates = ["NEON_CONNECTION_STRING", "DATABASE_URL", "database_url"]
    for key in candidates:
        try:
            value = st.secrets.get(key)
            if value:
                return str(value)
        except Exception:
            pass
        value = os.getenv(key)
        if value:
            return value

    # Opsi alternatif bila secrets disimpan dalam section [neon]
    try:
        neon = st.secrets.get("neon", {})
        for key in ("connection_string", "url", "database_url"):
            if neon.get(key):
                return str(neon[key])
    except Exception:
        pass
    return None


def read_table(conn, table_name: str) -> pd.DataFrame:
    # Nama tabel ditentukan tetap oleh aplikasi, bukan input pengguna.
    with conn.cursor() as cur:
        cur.execute(f'SELECT * FROM "{table_name}"')
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
    return pd.DataFrame(rows, columns=columns)


@st.cache_data(ttl=300, show_spinner=False)
def load_neon_data(connection_string: str) -> tuple[dict[str, pd.DataFrame], list[str], bool]:
    tables = {
        "kecamatan": "sawit_kecamatan_pusat",
        "kabupaten": "sawit_kabupaten",
        "harga": "harga_tbs_kabupaten",
    }
    result: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    conn = None
    try:
        conn = psycopg2.connect(connection_string, connect_timeout=10)
        for key, table in tables.items():
            try:
                result[key] = read_table(conn, table)
            except Exception as exc:
                conn.rollback()
                result[key] = pd.DataFrame()
                errors.append(f"Tabel {table}: {exc.__class__.__name__} — {exc}")
        return result, errors, True
    except Exception as exc:
        errors.append(f"Koneksi Neon: {exc.__class__.__name__} — {exc}")
        return {}, errors, False
    finally:
        if conn is not None:
            conn.close()


def load_reference_data() -> dict[str, pd.DataFrame]:
    return {
        "kecamatan": load_csv("kecamatan_referensi.csv"),
        "kabupaten": load_csv("kabupaten_referensi.csv"),
        "harga": load_csv("harga_tbs_referensi.csv"),
    }


def standardize_columns(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Pastikan nama kolom dan tipe dasar konsisten untuk tampilan dashboard."""
    out = {key: df.copy() for key, df in data.items()}
    for key in out:
        out[key].columns = [str(c).lower().strip() for c in out[key].columns]

    kec = out.get("kecamatan", pd.DataFrame())
    if not kec.empty:
        defaults = {
            "kode_data": None, "kabupaten": None, "kecamatan": None,
            "komoditas": "Kelapa Sawit", "tahun": None,
            "luas_tm_ha": None, "luas_total_ha": None,
            "produksi_ton": None, "harga_tbs_rp_kg": None,
            "tingkat_harga": None, "periode_harga": None,
            "sumber_data": None, "wilayah_sumber": None,
        }
        for col, default in defaults.items():
            if col not in kec.columns:
                kec[col] = default
        for col in ["tahun", "luas_tm_ha", "luas_total_ha", "produksi_ton", "harga_tbs_rp_kg"]:
            kec[col] = pd.to_numeric(kec[col], errors="coerce")
        kec["tahun"] = pd.to_numeric(kec["tahun"], errors="coerce").astype("Int64")
        kec["luas_analisis_ha"] = kec["luas_tm_ha"].combine_first(kec["luas_total_ha"])
        kec["produktivitas_ton_ha"] = kec["produksi_ton"] / kec["luas_analisis_ha"].replace({0: pd.NA})
        kec["harga_tahun"] = kec["periode_harga"].astype(str).str.extract(r"(20\d{2})", expand=False)
        kec["harga_tahun"] = pd.to_numeric(kec["harga_tahun"], errors="coerce").astype("Int64")
        kec["cek_tahun_harga"] = kec["harga_tahun"].notna() & kec["harga_tahun"].eq(kec["tahun"])
        kec["status_data"] = "Belum lengkap"
        lengkap = kec["luas_analisis_ha"].notna() & kec["produksi_ton"].notna() & kec["harga_tbs_rp_kg"].notna()
        sama_tahun = kec["cek_tahun_harga"].fillna(False)
        periode_tidak_jelas = lengkap & kec["harga_tahun"].isna()
        kec.loc[lengkap & sama_tahun, "status_data"] = "Lengkap (tahun cocok)"
        kec.loc[periode_tidak_jelas, "status_data"] = "Periode harga belum jelas"
        kec.loc[lengkap & kec["harga_tahun"].notna() & ~sama_tahun, "status_data"] = "Tahun tidak sama"
        kec["anomali_produktivitas"] = kec["produktivitas_ton_ha"].notna() & ~kec["produktivitas_ton_ha"].between(10, 30)
        out["kecamatan"] = kec

    kab = out.get("kabupaten", pd.DataFrame())
    if not kab.empty:
        for col in ["tahun", "luas_ha", "produksi_ton"]:
            if col in kab.columns:
                kab[col] = pd.to_numeric(kab[col], errors="coerce")
        if "tahun" in kab.columns:
            kab["tahun"] = pd.to_numeric(kab["tahun"], errors="coerce").astype("Int64")
        if {"luas_ha", "produksi_ton"}.issubset(kab.columns):
            kab["produktivitas_ton_ha"] = kab["produksi_ton"] / kab["luas_ha"].replace({0: pd.NA})

    harga = out.get("harga", pd.DataFrame())
    if not harga.empty:
        for col in ["harga_rp_kg"]:
            if col in harga.columns:
                harga[col] = pd.to_numeric(harga[col], errors="coerce")
        if "periode" in harga.columns:
            harga["tahun_periode"] = harga["periode"].astype(str).str.extract(r"(20\d{2})", expand=False)
    return out


connection_string = get_connection_string()
source_mode = "Referensi lokal"
connection_ok = False
load_errors: list[str] = []

if connection_string:
    neon_data, load_errors, connection_ok = load_neon_data(connection_string)
    has_any_neon_rows = connection_ok and any(not df.empty for df in neon_data.values())
    if has_any_neon_rows:
        raw_data = neon_data
        source_mode = "Database Neon"
    else:
        raw_data = load_reference_data()
        source_mode = "Referensi lokal (fallback)"
else:
    raw_data = load_reference_data()

DATA = standardize_columns(raw_data)
df_kec = DATA.get("kecamatan", pd.DataFrame())
df_kab = DATA.get("kabupaten", pd.DataFrame())
df_harga = DATA.get("harga", pd.DataFrame())

# -----------------------------
# Helper tampilan
# -----------------------------
def rupiah(value: Any, decimals: int = 0) -> str:
    if pd.isna(value):
        return "—"
    return "Rp " + f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def angka(value: Any, decimals: int = 0) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def hero(kicker: str, title: str, description: str) -> None:
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{kicker}</div><h1>{title}</h1><p>{description}</p></div>',
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="section-title">{title}</div><div class="section-sub">{subtitle}</div>', unsafe_allow_html=True)


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(message: str) -> None:
    st.info(message)


def nice_chart(fig, height: int = 360) -> None:
    fig.update_layout(
        height=height,
        margin=dict(l=18, r=18, t=35, b=25),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color="#496257", size=11),
        title_font=dict(family="Manrope", size=15, color="#183f33"),
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False, linecolor="#e6eee8")
    fig.update_yaxes(gridcolor="#edf2ee", zeroline=False)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# -----------------------------
# Sidebar navigasi + filter umum
# -----------------------------
with st.sidebar:
    st.markdown("<div style='font-size:11px;letter-spacing:2px;font-weight:800;color:#a9ddc4'>SISTEM INFORMASI PERKEBUNAN</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-family:Manrope;font-size:24px;font-weight:800;line-height:1.1;margin:8px 0 3px'>🌴 SIM-SAWIT<br>SUMUT</div>", unsafe_allow_html=True)
    st.caption("Dashboard komoditas kelapa sawit Provinsi Sumatera Utara")
    st.markdown("---")
    page = st.radio(
        "MENU UTAMA",
        ["Ringkasan", "Analisis Kabupaten", "Data Kecamatan", "Harga TBS", "Kualitas Data", "Tentang Sistem"],
        label_visibility="visible",
    )
    st.markdown("---")
    st.markdown("**Status sumber data**")
    if source_mode == "Database Neon":
        st.success("Terhubung ke Neon")
    else:
        st.warning("Menggunakan data referensi lokal")
    st.caption(f"Sumber aktif: {source_mode}")
    if st.button("↻ Muat ulang data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.caption("SIM-SAWIT SUMUT • Proyek basis data Agribisnis")

# -----------------------------
# Informasi status database
# -----------------------------
if source_mode != "Database Neon":
    st.warning(
        "Dashboard sedang menggunakan **data referensi yang disertakan dalam proyek**. "
        "Untuk menampilkan data terbaru dari Neon, tambahkan connection string database pusat "
        "pada Streamlit Secrets. Data referensi tidak dicampur dengan data Neon secara diam-diam."
    )
if load_errors:
    with st.expander("Detail koneksi / tabel Neon", expanded=False):
        for error in load_errors:
            st.code(error)

# -----------------------------
# PAGE 1: RINGKASAN
# -----------------------------
if page == "Ringkasan":
    hero(
        "PUSAT INFORMASI KELAPA SAWIT SUMATERA UTARA",
        "Pantau data. Baca potensi. Ambil keputusan.",
        "SIM-SAWIT SUMUT menyajikan ringkasan luas perkebunan, produksi, produktivitas, dan harga TBS dengan penanda sumber serta tahun data agar analisis tetap transparan.",
    )

    kab_latest_year = None
    if not df_kab.empty and "tahun" in df_kab.columns and df_kab["tahun"].notna().any():
        kab_latest_year = int(df_kab["tahun"].dropna().max())
        kab_latest = df_kab[df_kab["tahun"] == kab_latest_year].copy()
    else:
        kab_latest = pd.DataFrame()

    total_prod = kab_latest["produksi_ton"].sum(min_count=1) if not kab_latest.empty and "produksi_ton" in kab_latest else pd.NA
    total_area = kab_latest["luas_ha"].sum(min_count=1) if not kab_latest.empty and "luas_ha" in kab_latest else pd.NA
    avg_yield = (total_prod / total_area) if pd.notna(total_prod) and pd.notna(total_area) and total_area else pd.NA
    count_regions = kab_latest["kabupaten"].nunique() if not kab_latest.empty and "kabupaten" in kab_latest else 0
    latest_price = df_harga["harga_rp_kg"].mean() if not df_harga.empty and "harga_rp_kg" in df_harga else pd.NA

    cols = st.columns(4)
    with cols[0]: metric_card("Total produksi", f"{angka(total_prod/1_000_000,2)} juta ton" if pd.notna(total_prod) else "—", f"Agregat kabupaten tahun {kab_latest_year}" if kab_latest_year else "Data agregat belum tersedia")
    with cols[1]: metric_card("Luas perkebunan", f"{angka(total_area,0)} ha" if pd.notna(total_area) else "—", f"Agregat wilayah tahun {kab_latest_year}" if kab_latest_year else "Data luas kabupaten belum tersedia")
    with cols[2]: metric_card("Produktivitas rata-rata", f"{angka(avg_yield,2)} ton/ha" if pd.notna(avg_yield) else "—", "Produksi dibagi luas pada tahun yang sama")
    with cols[3]: metric_card("Kabupaten terdata", str(count_regions), f"Harga rata-rata referensi: {rupiah(latest_price)}/kg" if pd.notna(latest_price) else "Harga TBS belum tersedia")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    a, b = st.columns([1.35, 1])
    with a:
        section("Produksi sawit per kabupaten", f"Perbandingan data agregat tahun {kab_latest_year if kab_latest_year else '—'} • satuan ton")
        if not kab_latest.empty and {"kabupaten", "produksi_ton"}.issubset(kab_latest.columns):
            plotdf = kab_latest.dropna(subset=["produksi_ton"]).sort_values("produksi_ton", ascending=True)
            fig = px.bar(plotdf, x="produksi_ton", y="kabupaten", orientation="h", text_auto=".3s", color="produksi_ton", color_continuous_scale=["#b8e3c8", "#16845b"])
            fig.update_coloraxes(showscale=False)
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(xaxis_title="Produksi (ton)", yaxis_title="", title="Kabupaten dengan produksi terbesar")
            nice_chart(fig, 365)
        else:
            empty_state("Belum ada data produksi kabupaten dari sumber aktif.")
    with b:
        section("Komposisi luas perkebunan", "Proporsi luas dari kabupaten yang tersedia")
        if not kab_latest.empty and {"kabupaten", "luas_ha"}.issubset(kab_latest.columns):
            plotdf = kab_latest.dropna(subset=["luas_ha"])
            fig = px.pie(plotdf, names="kabupaten", values="luas_ha", hole=0.62, color_discrete_sequence=["#146c50", "#31a477", "#77c69b", "#bddfc7", "#e0efe4"])
            fig.update_traces(textposition="inside", textinfo="percent")
            fig.update_layout(title="Bagian luas perkebunan", showlegend=True, legend=dict(orientation="h", y=-0.14))
            nice_chart(fig, 365)
        else:
            empty_state("Belum ada data luas kabupaten dari sumber aktif.")

    section("Sorotan data", "Insight dihitung otomatis dari data yang sedang ditampilkan")
    insight_cols = st.columns(3)
    if not kab_latest.empty:
        top_prod = kab_latest.dropna(subset=["produksi_ton"]).sort_values("produksi_ton", ascending=False).head(1)
        top_area = kab_latest.dropna(subset=["luas_ha"]).sort_values("luas_ha", ascending=False).head(1)
        top_yield = kab_latest.dropna(subset=["produktivitas_ton_ha"]).sort_values("produktivitas_ton_ha", ascending=False).head(1)
        with insight_cols[0]:
            if not top_prod.empty:
                r = top_prod.iloc[0]
                st.markdown(f"<div class='insight-card'><b>🏆 Produksi tertinggi</b><br><span style='font-size:19px;font-weight:800'>{r['kabupaten']}</span><br>{angka(r['produksi_ton'],0)} ton pada {kab_latest_year}</div>", unsafe_allow_html=True)
        with insight_cols[1]:
            if not top_area.empty:
                r = top_area.iloc[0]
                st.markdown(f"<div class='insight-card'><b>🌱 Luas terbesar</b><br><span style='font-size:19px;font-weight:800'>{r['kabupaten']}</span><br>{angka(r['luas_ha'],0)} hektar pada {kab_latest_year}</div>", unsafe_allow_html=True)
        with insight_cols[2]:
            if not top_yield.empty:
                r = top_yield.iloc[0]
                st.markdown(f"<div class='insight-card'><b>📈 Produktivitas tertinggi</b><br><span style='font-size:19px;font-weight:800'>{r['kabupaten']}</span><br>{angka(r['produktivitas_ton_ha'],2)} ton/ha pada {kab_latest_year}</div>", unsafe_allow_html=True)
    else:
        st.info("Insight kabupaten akan muncul setelah tabel sawit_kabupaten terisi di database pusat.")

    section("Data yang tersedia", "Ringkasan berdasarkan tiga tabel utama SIM-SAWIT SUMUT")
    d1, d2, d3 = st.columns(3)
    with d1: metric_card("Baris data kecamatan", angka(len(df_kec)), "sawit_kecamatan_pusat")
    with d2: metric_card("Baris data kabupaten", angka(len(df_kab)), "sawit_kabupaten")
    with d3: metric_card("Baris harga TBS", angka(len(df_harga)), "harga_tbs_kabupaten")

# -----------------------------
# PAGE 2: ANALISIS KABUPATEN
# -----------------------------
elif page == "Analisis Kabupaten":
    hero("ANALISIS WILAYAH", "Membandingkan kinerja perkebunan", "Lihat perkembangan luas, produksi, dan produktivitas pada tingkat kabupaten. Gunakan filter tahun untuk menjaga perbandingan tetap setara.")
    if df_kab.empty:
        empty_state("Tabel sawit_kabupaten belum berisi data. Pastikan data kabupaten sudah dimasukkan ke database pusat Neon.")
    else:
        years = sorted([int(x) for x in df_kab["tahun"].dropna().unique()], reverse=True) if "tahun" in df_kab else []
        if years:
            selected_year = st.selectbox("Pilih tahun data", years, index=0)
            selected = df_kab[df_kab["tahun"] == selected_year].copy()
        else:
            selected_year = None
            selected = df_kab.copy()
        if "kabupaten" in selected:
            regions = ["Semua kabupaten"] + sorted(selected["kabupaten"].dropna().unique().tolist())
            chosen_region = st.selectbox("Filter kabupaten", regions)
            if chosen_region != "Semua kabupaten":
                selected = selected[selected["kabupaten"] == chosen_region]

        c1, c2, c3 = st.columns(3)
        with c1: metric_card("Total luas", f"{angka(selected['luas_ha'].sum(min_count=1),0)} ha" if "luas_ha" in selected else "—", f"Tahun {selected_year or '—'}")
        with c2: metric_card("Total produksi", f"{angka(selected['produksi_ton'].sum(min_count=1),0)} ton" if "produksi_ton" in selected else "—", f"Tahun {selected_year or '—'}")
        with c3:
            y = selected["produksi_ton"].sum(min_count=1) / selected["luas_ha"].sum(min_count=1) if {"produksi_ton", "luas_ha"}.issubset(selected.columns) and selected["luas_ha"].sum(min_count=1) else pd.NA
            metric_card("Produktivitas agregat", f"{angka(y,2)} ton/ha" if pd.notna(y) else "—", "Total produksi ÷ total luas")

        left, right = st.columns(2)
        with left:
            section("Luas vs produksi", "Keduanya ditampilkan berdasarkan kabupaten dan tahun terpilih")
            if {"kabupaten", "luas_ha", "produksi_ton"}.issubset(selected.columns):
                f = px.scatter(selected, x="luas_ha", y="produksi_ton", text="kabupaten", size="produksi_ton", color="produktivitas_ton_ha" if "produktivitas_ton_ha" in selected else None, color_continuous_scale="Greens", labels={"luas_ha":"Luas (ha)","produksi_ton":"Produksi (ton)","produktivitas_ton_ha":"Ton/ha"})
                f.update_traces(textposition="top center")
                nice_chart(f, 360)
        with right:
            section("Produktivitas antarwilayah", "Produksi per hektar pada tahun terpilih")
            if {"kabupaten", "produktivitas_ton_ha"}.issubset(selected.columns):
                plotdf = selected.dropna(subset=["produktivitas_ton_ha"]).sort_values("produktivitas_ton_ha")
                f = px.bar(plotdf, x="produktivitas_ton_ha", y="kabupaten", orientation="h", text_auto=".2f", color="produktivitas_ton_ha", color_continuous_scale=["#d0ead9","#17845b"])
                f.update_coloraxes(showscale=False)
                f.update_layout(xaxis_title="Ton per hektar", yaxis_title="")
                nice_chart(f, 360)

        section("Tabel perbandingan kabupaten", "Produktivitas dihitung dari produksi dibagi luas, hanya untuk baris dengan kedua angka tersedia")
        show_cols = [c for c in ["kabupaten", "tahun", "luas_ha", "produksi_ton", "produktivitas_ton_ha", "sumber_data"] if c in selected.columns]
        table = selected[show_cols].copy()
        if "luas_ha" in table: table["luas_ha"] = table["luas_ha"].map(lambda x: angka(x, 2))
        if "produksi_ton" in table: table["produksi_ton"] = table["produksi_ton"].map(lambda x: angka(x, 2))
        if "produktivitas_ton_ha" in table: table["produktivitas_ton_ha"] = table["produktivitas_ton_ha"].map(lambda x: angka(x, 2))
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button("⬇ Unduh tabel kabupaten (CSV)", selected.to_csv(index=False).encode("utf-8-sig"), file_name=f"analisis_kabupaten_{selected_year or 'semua'}.csv", mime="text/csv")

        # Tren hanya dibentuk saat ada dua tahun atau lebih untuk kabupaten yang sama.
        if df_kab["tahun"].nunique() > 1:
            section("Perubahan produksi dari waktu ke waktu", "Tren ini hanya membandingkan tahun yang tersedia pada tabel kabupaten")
            f = px.line(df_kab.dropna(subset=["produksi_ton"]), x="tahun", y="produksi_ton", color="kabupaten", markers=True, labels={"tahun":"Tahun","produksi_ton":"Produksi (ton)","kabupaten":"Kabupaten"})
            nice_chart(f, 360)

# -----------------------------
# PAGE 3: DATA KECAMATAN
# -----------------------------
elif page == "Data Kecamatan":
    hero("DETAIL KECAMATAN", "Telusuri data hingga tingkat kecamatan", "Filter wilayah dan tahun untuk melihat luas tanaman menghasilkan, produksi, produktivitas, serta ketersediaan harga TBS. Baris yang tidak lengkap tetap ditampilkan sebagai NULL/kosong.")
    if df_kec.empty:
        empty_state("Tabel sawit_kecamatan_pusat belum memiliki baris data pada sumber aktif.")
    else:
        regions = sorted(df_kec["kabupaten"].dropna().astype(str).unique().tolist()) if "kabupaten" in df_kec else []
        chosen_region = st.selectbox("Pilih kabupaten", ["Semua kabupaten"] + regions)
        filtered = df_kec.copy()
        if chosen_region != "Semua kabupaten":
            filtered = filtered[filtered["kabupaten"].astype(str) == chosen_region]
        years = sorted([int(x) for x in filtered["tahun"].dropna().unique()], reverse=True) if "tahun" in filtered else []
        if years:
            year_choice = st.selectbox("Pilih tahun pencatatan kecamatan", ["Semua tahun"] + years)
            if year_choice != "Semua tahun":
                filtered = filtered[filtered["tahun"] == year_choice]
        else:
            year_choice = "Semua tahun"

        complete_count = int((filtered["status_data"] == "Lengkap (tahun cocok)").sum()) if "status_data" in filtered else 0
        anomalies = int(filtered["anomali_produktivitas"].sum()) if "anomali_produktivitas" in filtered else 0
        m1, m2, m3, m4 = st.columns(4)
        with m1: metric_card("Jumlah baris", angka(len(filtered)), "Data kecamatan terfilter")
        with m2: metric_card("Data lengkap", angka(complete_count), "Luas + produksi + harga; cek tahun")
        with m3: metric_card("Anomali produktivitas", angka(anomalies), "Di luar rentang penanda 10–30 ton/ha")
        with m4: metric_card("Kabupaten terpilih", "Semua" if chosen_region == "Semua kabupaten" else chosen_region, str(filtered["kabupaten"].nunique()) + " kabupaten" if "kabupaten" in filtered else "")

        if "produksi_ton" in filtered and filtered["produksi_ton"].notna().any():
            section("Produksi per kecamatan", "Hanya kecamatan dengan angka produksi yang tersedia")
            plotdf = filtered.dropna(subset=["produksi_ton"]).sort_values("produksi_ton", ascending=True)
            if not plotdf.empty:
                f = px.bar(plotdf, x="produksi_ton", y="kecamatan", color="kabupaten", orientation="h", text_auto=".3s", labels={"produksi_ton":"Produksi (ton)","kecamatan":"Kecamatan"})
                f.update_layout(yaxis_title="", xaxis_title="Produksi (ton)")
                nice_chart(f, max(330, min(650, 30 * len(plotdf) + 100)))

        section("Tabel data kecamatan", "Kosong berarti data belum tersedia; jangan menafsirkan nilai kosong sebagai nol")
        wanted = ["kabupaten", "kecamatan", "tahun", "luas_tm_ha", "luas_total_ha", "luas_analisis_ha", "produksi_ton", "produktivitas_ton_ha", "harga_tbs_rp_kg", "tingkat_harga", "periode_harga", "status_data", "sumber_data"]
        show_cols = [c for c in wanted if c in filtered.columns]
        table = filtered[show_cols].copy()
        numeric_cols = ["luas_tm_ha", "luas_total_ha", "luas_analisis_ha", "produksi_ton", "produktivitas_ton_ha", "harga_tbs_rp_kg"]
        for c in numeric_cols:
            if c in table:
                table[c] = table[c].map(lambda x: angka(x, 2) if pd.notna(x) else "NULL")
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button("⬇ Unduh data kecamatan (CSV)", filtered.to_csv(index=False).encode("utf-8-sig"), file_name="data_kecamatan_sawit.csv", mime="text/csv")

        anomaly_df = filtered[filtered.get("anomali_produktivitas", False) == True] if "anomali_produktivitas" in filtered else pd.DataFrame()
        if not anomaly_df.empty:
            st.markdown("<div class='warn-card'><b>⚠ Perlu verifikasi angka</b><br>Ada produktivitas yang berada di luar rentang penanda 10–30 ton/ha. Rentang ini hanya alat penyaring awal, bukan standar resmi atau bukti bahwa angka pasti salah.</div>", unsafe_allow_html=True)
            st.dataframe(anomaly_df[[c for c in ["kabupaten", "kecamatan", "tahun", "luas_analisis_ha", "produksi_ton", "produktivitas_ton_ha", "sumber_data"] if c in anomaly_df.columns]], use_container_width=True, hide_index=True)

# -----------------------------
# PAGE 4: HARGA TBS
# -----------------------------
elif page == "Harga TBS":
    hero("PEMANTAUAN HARGA", "Harga TBS per kabupaten", "Bandingkan harga TBS berdasarkan periode yang tercatat. Harga pada halaman ini adalah harga tingkat kabupaten, bukan harga khusus tiap kecamatan, kecuali sumber data menyatakan sebaliknya.")
    if df_harga.empty:
        empty_state("Tabel harga_tbs_kabupaten belum memiliki data pada sumber aktif.")
    else:
        if "periode" in df_harga.columns:
            periods = sorted(df_harga["periode"].dropna().astype(str).unique().tolist(), reverse=True)
            period_choice = st.selectbox("Periode harga", ["Semua periode"] + periods)
            filtered = df_harga.copy() if period_choice == "Semua periode" else df_harga[df_harga["periode"].astype(str) == period_choice].copy()
        else:
            filtered = df_harga.copy()
            period_choice = "Semua periode"
        if "kabupaten" in filtered:
            regions = ["Semua kabupaten"] + sorted(filtered["kabupaten"].dropna().astype(str).unique().tolist())
            region_choice = st.selectbox("Filter kabupaten", regions)
            if region_choice != "Semua kabupaten": filtered = filtered[filtered["kabupaten"].astype(str) == region_choice]
        price_mean = filtered["harga_rp_kg"].mean() if "harga_rp_kg" in filtered else pd.NA
        price_max = filtered["harga_rp_kg"].max() if "harga_rp_kg" in filtered else pd.NA
        price_min = filtered["harga_rp_kg"].min() if "harga_rp_kg" in filtered else pd.NA
        c1, c2, c3 = st.columns(3)
        with c1: metric_card("Rata-rata harga", rupiah(price_mean) + "/kg" if pd.notna(price_mean) else "—", period_choice)
        with c2: metric_card("Harga tertinggi", rupiah(price_max) + "/kg" if pd.notna(price_max) else "—", "Dari kabupaten terfilter")
        with c3: metric_card("Harga terendah", rupiah(price_min) + "/kg" if pd.notna(price_min) else "—", "Dari kabupaten terfilter")

        section("Perbandingan harga TBS", "Harga dalam rupiah per kilogram")
        if {"kabupaten", "harga_rp_kg"}.issubset(filtered.columns):
            plotdf = filtered.dropna(subset=["harga_rp_kg"]).sort_values("harga_rp_kg", ascending=True)
            f = px.bar(plotdf, x="harga_rp_kg", y="kabupaten", orientation="h", text=plotdf["harga_rp_kg"].map(lambda x: rupiah(x)), color="harga_rp_kg", color_continuous_scale=["#cce9d7", "#16845b"], labels={"harga_rp_kg":"Harga TBS (Rp/kg)","kabupaten":"Kabupaten"})
            f.update_coloraxes(showscale=False)
            f.update_traces(textposition="outside", cliponaxis=False)
            f.update_layout(yaxis_title="", xaxis_title="Harga (Rp/kg)")
            nice_chart(f, max(330, min(650, 28 * len(plotdf) + 100)))

        section("Rincian harga dan sumber", "Periode dan sumber asli harus dipertahankan pada saat mengutip angka")
        st.dataframe(filtered, use_container_width=True, hide_index=True)
        st.download_button("⬇ Unduh harga TBS (CSV)", filtered.to_csv(index=False).encode("utf-8-sig"), file_name="harga_tbs_sawit.csv", mime="text/csv")
        st.markdown("<div class='warn-card'><b>Catatan interpretasi</b><br>Harga TBS dapat berubah menurut periode penetapan. Jangan membandingkan harga dari periode berbeda tanpa mencantumkan tanggal/periode. Harga kabupaten juga tidak otomatis mewakili harga transaksi setiap petani atau setiap kecamatan.</div>", unsafe_allow_html=True)

# -----------------------------
# PAGE 5: KUALITAS DATA
# -----------------------------
elif page == "Kualitas Data":
    hero("VALIDASI & TRANSPARANSI", "Periksa kelengkapan sebelum analisis", "Halaman ini memisahkan data yang lengkap, data yang masih NULL, perbedaan tahun, serta angka yang perlu diverifikasi. Validasi membantu mencegah kesimpulan yang menyesatkan.")
    total_rows = len(df_kec)
    if not df_kec.empty:
        area_ok = df_kec["luas_analisis_ha"].notna() if "luas_analisis_ha" in df_kec else pd.Series(False, index=df_kec.index)
        prod_ok = df_kec["produksi_ton"].notna() if "produksi_ton" in df_kec else pd.Series(False, index=df_kec.index)
        price_ok = df_kec["harga_tbs_rp_kg"].notna() if "harga_tbs_rp_kg" in df_kec else pd.Series(False, index=df_kec.index)
        all_ok = area_ok & prod_ok & price_ok
        same_year = (df_kec["harga_tahun"].notna() & df_kec["tahun"].eq(df_kec["harga_tahun"])).fillna(False) if {"harga_tahun", "tahun"}.issubset(df_kec.columns) else pd.Series(False, index=df_kec.index)
        comparable = all_ok & same_year
        bad_year = all_ok & ~same_year
        missing_area = int((~area_ok).sum())
        missing_prod = int((~prod_ok).sum())
        missing_price = int((~price_ok).sum())
        anomalous = int(df_kec["anomali_produktivitas"].sum()) if "anomali_produktivitas" in df_kec else 0
    else:
        area_ok = prod_ok = price_ok = all_ok = same_year = comparable = bad_year = pd.Series(dtype=bool)
        missing_area = missing_prod = missing_price = anomalous = 0

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Total baris kecamatan", angka(total_rows), "Semua tahun yang tersedia")
    with c2: metric_card("Lengkap & tahun cocok", angka(int(comparable.sum())), "Luas + produksi + harga")
    with c3: metric_card("Harga beda tahun", angka(int(bad_year.sum())), "Lengkap tetapi tahun tidak cocok")
    with c4: metric_card("Anomali produktivitas", angka(anomalous), "Di luar rentang 10–30 ton/ha")

    section("Kelengkapan setiap variabel", "Persentase baris kecamatan yang memiliki nilai")
    if total_rows:
        completeness = pd.DataFrame({"Variabel": ["Luas", "Produksi", "Harga TBS"], "Terisi": [int(area_ok.sum()), int(prod_ok.sum()), int(price_ok.sum())], "Kosong": [missing_area, missing_prod, missing_price]})
        completeness["Persentase terisi (%)"] = completeness["Terisi"] / total_rows * 100
        f = px.bar(completeness, x="Variabel", y="Persentase terisi (%)", text=completeness["Persentase terisi (%)"].map(lambda x: f"{x:.1f}%"), color="Persentase terisi (%)", color_continuous_scale=["#f4d58e", "#16845b"])
        f.update_coloraxes(showscale=False)
        f.update_yaxes(range=[0, 110], ticksuffix="%")
        f.update_layout(xaxis_title="", yaxis_title="Kelengkapan")
        nice_chart(f, 300)
        st.dataframe(completeness, use_container_width=True, hide_index=True)
    else:
        empty_state("Belum ada baris data kecamatan untuk divalidasi.")

    section("Validasi syarat minimal 4 kecamatan", "Satu kabupaten dinilai memenuhi apabila memiliki sedikitnya empat baris kecamatan dengan luas, produksi, dan harga terisi serta tahun data dapat dicocokkan")
    if not df_kec.empty and "kabupaten" in df_kec:
        val = df_kec.copy()
        val["baris_lengkap_tahun"] = comparable
        summary = val.groupby("kabupaten", dropna=False).agg(jumlah_baris=("kecamatan", "count"), kecamatan_lengkap=("baris_lengkap_tahun", "sum")).reset_index()
        summary["status_minimal_4"] = summary["kecamatan_lengkap"].apply(lambda n: "MEMENUHI" if n >= 4 else "BELUM MEMENUHI")
        st.dataframe(summary, use_container_width=True, hide_index=True)
        passed = summary[summary["kecamatan_lengkap"] >= 4]
        if passed.empty:
            st.markdown("<div class='warn-card'><b>Belum ada kabupaten yang memenuhi validasi.</b><br>Lengkapi data asli yang belum tersedia. Jangan mengisi harga atau produksi dengan angka perkiraan hanya untuk meloloskan validasi.</div>", unsafe_allow_html=True)
        else:
            st.success("Kabupaten yang memenuhi validasi: " + ", ".join(passed["kabupaten"].astype(str).tolist()))

    section("Catatan kualitas dari sumber referensi", "Catatan ini mengikuti temuan pada bahan data awal")
    st.markdown("""
    <div class='info-card'>
      <b>1. Langkat — data kecamatan tahun 2017</b><br>
      Terdapat 12 kecamatan dengan luas tanaman menghasilkan dan produksi. Jumlah produksi yang tercatat adalah 461.248,8 ton, sedangkan total kabupaten yang disebut pada sumber adalah 751.413,46 ton. Artinya, daftar yang tersedia belum mencakup seluruh kecamatan. Produktivitas Salapian sekitar 1,8 ton/ha dan perlu diverifikasi karena jauh di bawah kecamatan lainnya.<br><br>
      <b>2. Labuhanbatu Selatan — data luas tahun 2020</b><br>
      Lima kecamatan memiliki data luas, tetapi produksi per kecamatan belum tersedia. Jumlah luas lima kecamatan adalah 42.930 ha, sementara total yang tertulis pada sumber 42.839 ha, terdapat selisih 91 ha.<br><br>
      <b>3. Harga TBS — periode November 2025</b><br>
      Harga yang tersedia merupakan harga tingkat kabupaten dan tidak otomatis menjadi harga tingkat kecamatan. Data harga berubah menurut periode penetapan.<br><br>
      <b>4. Prinsip penggunaan</b><br>
      Data dari tahun atau tingkat wilayah yang berbeda tidak boleh disatukan seolah-olah satu observasi yang sama. Kolom kosong tetap dipertahankan sebagai NULL.
    </div>
    """, unsafe_allow_html=True)

# -----------------------------
# PAGE 6: TENTANG SISTEM
# -----------------------------
elif page == "Tentang Sistem":
    hero("PROFIL APLIKASI", "SIM-SAWIT SUMUT", "Sistem informasi sederhana untuk mengintegrasikan, menampilkan, dan menganalisis data perkebunan kelapa sawit di Sumatera Utara.")
    left, right = st.columns([1.2, 1])
    with left:
        section("Tujuan sistem", "Dibangun untuk kebutuhan pembelajaran basis data dan analisis agribisnis")
        st.markdown("""
        <div class='info-card'>
          SIM-SAWIT SUMUT menghubungkan data tingkat kecamatan dan kabupaten dengan harga TBS. Data dikelola melalui PostgreSQL pada Neon, kemudian dibaca oleh aplikasi Streamlit untuk menyajikan indikator, tabel, grafik, dan pemeriksaan kualitas data.<br><br>
          <b>Fokus informasi:</b><br>
          • Luas tanaman menghasilkan dan luas total (hektar)<br>
          • Produksi TBS (ton)<br>
          • Produktivitas (ton/ha), dihitung otomatis<br>
          • Harga TBS (Rp/kg), beserta periode dan tingkat wilayah<br>
          • Sumber data, tahun, dan kelengkapan pencatatan
        </div>
        """, unsafe_allow_html=True)
        section("Struktur tabel Neon", "Aplikasi membaca tabel berikut dari database pusat")
        schema = pd.DataFrame([
            ["sawit_kecamatan_pusat", "Data kecamatan terintegrasi"],
            ["sawit_kabupaten", "Rekap luas dan produksi tingkat kabupaten"],
            ["harga_tbs_kabupaten", "Harga TBS tingkat kabupaten per periode"],
        ], columns=["Nama tabel", "Fungsi"])
        st.dataframe(schema, use_container_width=True, hide_index=True)
    with right:
        section("Status aplikasi", "Informasi teknis")
        st.markdown(f"<div class='soft-card'><b>Sumber aktif</b><br>{source_mode}<hr><b>Kecamatan</b><br>{len(df_kec)} baris<hr><b>Kabupaten</b><br>{len(df_kab)} baris<hr><b>Harga</b><br>{len(df_harga)} baris<hr><b>Waktu akses</b><br>{datetime.now().strftime('%d-%m-%Y %H:%M')}</div>", unsafe_allow_html=True)
        section("Pengingat keamanan")
        st.markdown("<div class='warn-card'>Jangan mengunggah connection string Neon, password, atau file <code>secrets.toml</code> ke repository GitHub. Simpan kredensial di Streamlit Secrets.</div>", unsafe_allow_html=True)

st.markdown("<div style='text-align:center;color:#8da197;font-size:10px;padding:25px 0 8px'>SIM-SAWIT SUMUT • Dashboard data kelapa sawit Sumatera Utara • Data kosong tidak diartikan sebagai nol</div>", unsafe_allow_html=True)
