from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import streamlit as st
from supabase import Client, create_client

APP_TITLE = "São Validades"
DATE_FMT = "%d/%m/%Y %H:%M"
PRINT_DATE_FMT = "%d/%m/%Y %H:%M"
PRINTER_QUEUE = "POS9220"
TSPL_LABEL_WIDTH_MM = 60
TSPL_LABEL_HEIGHT_MM = 30
TSPL_GAP_MM = 2
BASE_DIR = Path(__file__).resolve().parent
ROOT_PRODUCTS_CSV_PATH = BASE_DIR / "products.csv"
LEGACY_PRODUCTS_CSV_PATH = BASE_DIR / "data" / "products.csv"
PRODUCTS_CSV_PATH = ROOT_PRODUCTS_CSV_PATH
PRODUCT_COLUMNS = ["id", "name", "category", "shelf_life_days", "storage", "active"]

PRINT_JOBS_TABLE = "print_jobs"


def get_supabase_client() -> Client:
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    return create_client(url, key)


def enqueue_print_job(launch: dict[str, Any]) -> tuple[bool, str]:
    tspl_label = build_tspl_label(launch)
    payload = {
        "launch_id": launch["id"],
        "product_name": launch["product_name"],
        "category": launch["category"],
        "storage": launch["storage"],
        "launched_at": launch["launched_at"],
        "expires_at": launch["expires_at"],
        "user_name": launch["user_name"],
        "tspl": tspl_label,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    try:
        client = get_supabase_client()
        client.table(PRINT_JOBS_TABLE).insert(payload).execute()
        return True, "Etiqueta enviada para o computador de impressão."
    except KeyError:
        return False, "Configure 'supabase_url' e 'supabase_key' em st.secrets antes de usar a fila."
    except Exception as exc:
        return False, f"Falha ao enviar para a fila: {exc}"




def default_products() -> list[dict[str, Any]]:
    return [
        {"id": 1, "name": "Farinha", "category": "Secos", "shelf_life_days": 30, "storage": "Ambiente", "active": True},
        {"id": 2, "name": "Leite", "category": "Refrigerados", "shelf_life_days": 3, "storage": "Refrigerado", "active": True},
        {"id": 3, "name": "Molho da Casa", "category": "Produção", "shelf_life_days": 5, "storage": "Refrigerado", "active": True},
        {"id": 4, "name": "Frango", "category": "Proteínas", "shelf_life_days": 2, "storage": "Refrigerado", "active": True},
    ]


def ensure_products_csv_location() -> None:
    ROOT_PRODUCTS_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ROOT_PRODUCTS_CSV_PATH.exists() and LEGACY_PRODUCTS_CSV_PATH.exists():
        ROOT_PRODUCTS_CSV_PATH.write_bytes(LEGACY_PRODUCTS_CSV_PATH.read_bytes())


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "sim", "yes", "y"}


def normalize_product_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": str(row.get("name", "")).strip(),
        "category": str(row.get("category", "Geral")).strip() or "Geral",
        "shelf_life_days": int(row.get("shelf_life_days", 1)),
        "storage": str(row.get("storage", "Ambiente")).strip() or "Ambiente",
        "active": normalize_bool(row.get("active", True)),
    }


def save_products_to_csv(products: list[dict[str, Any]]) -> None:
    ensure_products_csv_location()
    rows = [normalize_product_row(product) for product in products]
    df = pd.DataFrame(rows, columns=PRODUCT_COLUMNS)
    temp_path = PRODUCTS_CSV_PATH.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8-sig", newline="") as temp_file:
        df.to_csv(temp_file, index=False)
        temp_file.flush()
        os.fsync(temp_file.fileno())
    temp_path.replace(PRODUCTS_CSV_PATH)


def load_products_from_csv() -> list[dict[str, Any]]:
    ensure_products_csv_location()
    if not PRODUCTS_CSV_PATH.exists():
        products = default_products()
        save_products_to_csv(products)
        return products

    try:
        df = pd.read_csv(PRODUCTS_CSV_PATH)
    except Exception:
        products = default_products()
        save_products_to_csv(products)
        return products

    if df.empty:
        products = default_products()
        save_products_to_csv(products)
        return products

    for column in PRODUCT_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df = df[PRODUCT_COLUMNS].fillna("")
    products: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        try:
            products.append(normalize_product_row(row))
        except Exception:
            continue

    if not products:
        products = default_products()
        save_products_to_csv(products)
        return products

    products.sort(key=lambda item: item["id"])
    return products


def sync_products_from_csv() -> None:
    products = load_products_from_csv()
    st.session_state.products = products
    st.session_state.next_product_id = max((product["id"] for product in products), default=0) + 1


def persist_products() -> None:
    products_to_save = [normalize_product_row(product) for product in st.session_state.products]
    save_products_to_csv(products_to_save)
    reloaded_products = load_products_from_csv()
    st.session_state.products = reloaded_products
    st.session_state.next_product_id = max((product["id"] for product in reloaded_products), default=0) + 1


def init_state() -> None:
    defaults: dict[str, Any] = {
        "users": [
            {"id": 1, "username": "carol", "password": "12carol", "name": "Carolina", "role": "admin"},
            {"id": 1, "username": "cesar", "password": "12cesar", "name": "Cesar", "role": "funcionario"},
            {"id": 2, "username": "leila", "password": "12leila", "name": "João", "Leila": "funcionario"},
            {"id": 3, "username": "diego", "password": "12diego", "name": "Maria", "Diego": "funcionario"},
        ],
        "launches": [],
        "current_user": None,
        "selected_product_id": None,
        "last_label_launch_id": None,
        "next_launch_id": 1,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "products" not in st.session_state or "next_product_id" not in st.session_state:
        sync_products_from_csv()


def configure_page() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="✅", layout="wide")
    st.markdown(
        """
        <style>
            .block-container {max-width: 1200px; padding-top: 0.9rem; padding-bottom: 3rem;}
            .stButton > button {width: 100%; min-height: 2.9rem; border-radius: 14px; font-weight: 600; padding-top: 0.35rem; padding-bottom: 0.35rem;}
            .product-card {padding: 0.9rem 1rem; border: 1px solid rgba(128,128,128,0.25); border-radius: 16px; margin-bottom: 0.4rem;}
            .top-box {padding: 0.9rem 1rem; border-radius: 16px; background: rgba(120,120,120,0.08); margin-bottom: 0.8rem;}
            .small-muted {opacity: 0.8; font-size: 0.92rem;}
            .label-preview {padding: 1rem; border: 2px dashed rgba(128,128,128,0.4); border-radius: 16px; margin-top: 0.8rem;}
            .label-preview h4 {margin: 0 0 0.5rem 0;}
            .label-preview p {margin: 0.18rem 0;}
            .sticky-side {position: sticky; top: 0.8rem;}
            .side-panel {padding: 1rem; border: 1px solid rgba(128,128,128,0.25); border-radius: 16px; background: rgba(120,120,120,0.06);}
            .launch-row {padding: 0.75rem 0.9rem; border: 1px solid rgba(128,128,128,0.22); border-radius: 16px; margin-bottom: 0.5rem; background: #fff;}
            @media (max-width: 640px) {
                .block-container {padding-top: 0.6rem; padding-left: 0.6rem; padding-right: 0.6rem;}
                .stButton > button {min-height: 2.6rem; border-radius: 12px;}
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def export_payload() -> str:
    payload = {
        "users": st.session_state.users,
        "products": st.session_state.products,
        "launches": st.session_state.launches,
        "next_product_id": st.session_state.next_product_id,
        "next_launch_id": st.session_state.next_launch_id,
        "exported_at": datetime.now().isoformat(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def import_payload(raw: str) -> None:
    data = json.loads(raw)
    required = {"users", "products", "launches", "next_product_id", "next_launch_id"}
    if not required.issubset(data):
        raise ValueError("Arquivo inválido.")
    st.session_state.users = data["users"]
    st.session_state.products = [normalize_product_row(product) for product in data["products"]]
    st.session_state.launches = data["launches"]
    st.session_state.next_product_id = int(data["next_product_id"])
    st.session_state.next_launch_id = int(data["next_launch_id"])
    persist_products()


def active_products() -> list[dict[str, Any]]:
    return [p for p in st.session_state.products if p.get("active", True)]


def find_product(product_id: int) -> dict[str, Any] | None:
    for product in st.session_state.products:
        if product["id"] == product_id:
            return product
    return None


def find_launch(launch_id: int | None) -> dict[str, Any] | None:
    if launch_id is None:
        return None
    for launch in st.session_state.launches:
        if launch["id"] == launch_id:
            return launch
    return None


def current_user() -> dict[str, Any] | None:
    return st.session_state.current_user


def login(username: str, password: str) -> bool:
    for user in st.session_state.users:
        if user["username"] == username and user["password"] == password:
            st.session_state.current_user = user
            return True
    return False


def logout() -> None:
    st.session_state.current_user = None
    st.session_state.selected_product_id = None
    st.session_state.last_label_launch_id = None


def create_launch(product: dict[str, Any], user: dict[str, Any]) -> int:
    launched_at = datetime.now()
    expires_at = launched_at + timedelta(days=int(product["shelf_life_days"]))
    launch = {
        "id": st.session_state.next_launch_id,
        "product_id": product["id"],
        "product_name": product["name"],
        "category": product["category"],
        "storage": product["storage"],
        "shelf_life_days": int(product["shelf_life_days"]),
        "launched_at": launched_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "user_id": user["id"],
        "user_name": user["name"],
    }
    st.session_state.launches.insert(0, launch)
    st.session_state.next_launch_id += 1
    st.session_state.last_label_launch_id = launch["id"]
    return launch["id"]


def launches_df() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    now = datetime.now()
    for launch in st.session_state.launches:
        expires_at = datetime.fromisoformat(launch["expires_at"])
        if expires_at < now:
            status = "Vencido"
        elif expires_at <= now + timedelta(days=3):
            status = "Vence logo"
        else:
            status = "Ativo"
        rows.append(
            {
                "ID": launch["id"],
                "Produto": launch["product_name"],
                "Categoria": launch["category"],
                "Armazenamento": launch["storage"],
                "Lançado em": datetime.fromisoformat(launch["launched_at"]).strftime(DATE_FMT),
                "Vence em": expires_at.strftime(DATE_FMT),
                "Responsável": launch["user_name"],
                "Status": status,
            }
        )
    return pd.DataFrame(rows)


def sanitize_tspl_text(value: str, max_len: int = 28) -> str:
    cleaned = str(value).replace("\\", "/").replace(chr(34), "'").replace("\n", " ").strip()
    return cleaned[:max_len]


def build_tspl_label(launch: dict[str, Any]) -> str:
    launched_at = datetime.fromisoformat(launch["launched_at"])
    expires_at = datetime.fromisoformat(launch["expires_at"])

    product_name = sanitize_tspl_text(launch["product_name"], 18)
    category = sanitize_tspl_text(f"Cat: {launch['category']}", 24)
    storage = sanitize_tspl_text(f"Arm: {launch['storage']}", 24)
    launched_line = sanitize_tspl_text(
        f"Lanc: {launched_at.strftime(PRINT_DATE_FMT)}", 24
    )
    expiry_line = sanitize_tspl_text(
        f"VENC: {expires_at.strftime(PRINT_DATE_FMT)}", 24
    )
    user_line = sanitize_tspl_text(
        f"Resp: {launch['user_name']} ID:{launch['id']}", 24
    )

    x = 20
    y0 = 24
    step = 36

    return f"""SIZE {TSPL_LABEL_WIDTH_MM} mm,{TSPL_LABEL_HEIGHT_MM} mm
GAP {TSPL_GAP_MM} mm,0
DENSITY 6
SPEED 2
DIRECTION 0
REFERENCE 0,0
CLS
TEXT {x},{y0},"3",0,1,1,"{product_name}"
TEXT {x},{y0 + 48},"2",0,1,1,"{category}"
TEXT {x},{y0 + 48 + step},"2",0,1,1,"{storage}"
TEXT {x},{y0 + 48 + step * 2},"2",0,1,1,"{launched_line}"
TEXT {x},{y0 + 48 + step * 3},"2",0,1,1,"{expiry_line}"
TEXT {x},{y0 + 48 + step * 4 - 6},"2",0,1,1,"{user_line}"
PRINT 1
"""


def send_to_thermal_printer(tspl_label: str, printer_queue: str = PRINTER_QUEUE) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["lp", "-d", printer_queue, "-o", "raw"],
            input=tspl_label,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return False, "Comando 'lp' não encontrado. Instale e configure o CUPS no computador."
    except Exception as exc:
        return False, f"Erro ao enviar para a impressora: {exc}"

    if result.returncode == 0:
        output = (result.stdout or "").strip()
        return True, output or f"Etiqueta enviada para a fila {printer_queue}."

    error = (result.stderr or result.stdout or "Falha desconhecida ao imprimir.").strip()
    return False, error


def build_label_html(launch: dict[str, Any]) -> str:
    launched_at = datetime.fromisoformat(launch["launched_at"])
    expires_at = datetime.fromisoformat(launch["expires_at"])
    return f"""<!DOCTYPE html>
<html lang=\"pt-BR\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>Etiqueta {launch['product_name']}</title>
<style>
  @page {{ size: 60mm 40mm; margin: 0; }}
  body {{ margin: 0; font-family: Arial, sans-serif; }}
  .label {{ width: 60mm; height: 40mm; box-sizing: border-box; padding: 3mm; border: 1px solid #000; }}
  .title {{ font-size: 12pt; font-weight: bold; line-height: 1.1; margin-bottom: 2mm; }}
  .row {{ font-size: 8.5pt; margin: 0.8mm 0; }}
  .expiry {{ margin-top: 2mm; padding: 1.5mm; border: 1px solid #000; font-size: 10pt; font-weight: bold; }}
  .small {{ font-size: 7.5pt; }}
</style>
</head>
<body onload=\"window.print()\">
  <div class=\"label\">
    <div class=\"title\">{launch['product_name']}</div>
    <div class=\"row\"><strong>Categoria:</strong> {launch['category']}</div>
    <div class=\"row\"><strong>Armaz.:</strong> {launch['storage']}</div>
    <div class=\"row\"><strong>Produzido/Lançado:</strong> {launched_at.strftime(DATE_FMT)}</div>
    <div class=\"expiry\">VENC: {expires_at.strftime(PRINT_DATE_FMT)}</div>
    <div class=\"row small\">Resp.: {launch['user_name']} • ID {launch['id']}</div>
  </div>
</body>
</html>"""


def build_zpl_label(launch: dict[str, Any]) -> str:
    launched_at = datetime.fromisoformat(launch["launched_at"])
    expires_at = datetime.fromisoformat(launch["expires_at"])
    product_name = sanitize_zpl_text(launch["product_name"], 26)
    category = sanitize_zpl_text(launch["category"], 20)
    storage = sanitize_zpl_text(launch["storage"], 18)
    user_name = sanitize_zpl_text(launch["user_name"], 18)
    return f"""^XA
^CI28
^PW480
^LL320
^FO20,20^A0N,34,34^FD{product_name}^FS
^FO20,70^A0N,24,24^FDCat: {category}^FS
^FO20,100^A0N,24,24^FDArm: {storage}^FS
^FO20,130^A0N,24,24^FDLanc: {launched_at.strftime(PRINT_DATE_FMT)}^FS
^FO20,170^GB440,0,3^FS
^FO20,190^A0N,34,34^FDVENC: {expires_at.strftime(PRINT_DATE_FMT)}^FS
^FO20,240^A0N,22,22^FDResp: {user_name}  ID:{launch['id']}^FS
^XZ"""


def sanitize_zpl_text(value: str, max_len: int) -> str:
    cleaned = value.replace("^", " ").replace("~", " ").replace("\\", "/")
    return cleaned[:max_len]


def render_login() -> None:
    st.caption("Clique no produto para lançar e enviar a etiqueta para o computador que está com a impressora térmica USB.")
    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")
    st.markdown("<div class='small-muted'>Usuários de teste: admin / joao / maria — senha 1234</div>", unsafe_allow_html=True)
    if submitted:
        if login(username.strip(), password):
            st.rerun()
        st.error("Usuário ou senha inválidos.")


def render_header(user: dict[str, Any]) -> None:
    st.markdown(
        f"<div class='top-box'><strong>{user['name']}</strong> • {user['role'].title()}<br><span class='small-muted'>{datetime.now().strftime(DATE_FMT)}</span></div>",
        unsafe_allow_html=True,
    )
    if st.button("Sair", width='content'):
        logout()
        st.rerun()


def render_label_actions(launch: dict[str, Any]) -> None:
    launched_at = datetime.fromisoformat(launch["launched_at"])
    expires_at = datetime.fromisoformat(launch["expires_at"])
    st.markdown("### Etiqueta pronta para impressão")
    st.markdown(
        f"""
        <div class='label-preview'>
            <h4>{launch['product_name']}</h4>
            <p><strong>Categoria:</strong> {launch['category']}</p>
            <p><strong>Armazenamento:</strong> {launch['storage']}</p>
            <p><strong>Lançado em:</strong> {launched_at.strftime(DATE_FMT)}</p>
            <p><strong>Vencimento:</strong> {expires_at.strftime(PRINT_DATE_FMT)}</p>
            <p><strong>Responsável:</strong> {launch['user_name']}</p>
            <p><strong>ID:</strong> {launch['id']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    html_label = build_label_html(launch)
    tspl_label = build_tspl_label(launch)
    html_url = "data:text/html;charset=utf-8," + quote(html_label)

    st.link_button("Abrir etiqueta no navegador", html_url, width='stretch')
    p1, p2 = st.columns(2)
    p1.download_button(
        "Baixar etiqueta HTML",
        data=html_label,
        file_name=f"etiqueta_{launch['id']}.html",
        mime="text/html",
        width='stretch',
    )
    p2.download_button(
        "Baixar etiqueta TSPL (.tspl)",
        data=tspl_label,
        file_name=f"etiqueta_{launch['id']}.tspl",
        mime="text/plain",
        width='stretch',
    )

    if st.button("Enviar para a fila de impressão", key=f"print_now_{launch['id']}", type="primary", width='stretch'):
        ok, message = enqueue_print_job(launch)
        if ok:
            st.session_state.last_label_launch_id = None
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    st.caption("Formato térmico: TSPL 60x30 mm. A impressão sai no computador com a impressora USB e o print_agent ligado.")


def render_quick_launch(user: dict[str, Any]) -> None:
    products = active_products()
    if not products:
        st.info("Cadastre produtos para começar.")
        return

    st.session_state.selected_product_id = None
    search = st.text_input("Buscar produto", placeholder="Ex.: farinha")
    filtered = [p for p in products if search.lower() in p["name"].lower()] if search else products

    if not filtered:
        st.warning("Nenhum produto encontrado.")
        return

    for product in filtered:
        if st.button(
            product["name"],
            key=f"quick_launch_name_{product['id']}",
            width='stretch',
        ):
            launch_id = create_launch(product, user)
            launch = find_launch(launch_id)
            if launch is not None:
                ok, message = enqueue_print_job(launch)
                if ok:
                    st.toast(f"{product['name']} enviado para impressão.")
                else:
                    st.error(message)
            st.rerun()


def render_history(user: dict[str, Any]) -> None:
    st.subheader("Histórico")
    df = launches_df()
    if df.empty:
        st.info("Nenhum lançamento ainda.")
        return

    c1, c2 = st.columns(2)
    period = c1.selectbox("Período", ["Hoje", "7 dias", "30 dias", "Tudo"])
    if user["role"] == "admin":
        employees = ["Todos"] + sorted(df["Responsável"].unique().tolist())
    else:
        employees = [user["name"]]
    employee = c2.selectbox("Responsável", employees)

    base_df = df.copy()
    launched_series = pd.to_datetime(base_df["Lançado em"], format=DATE_FMT)
    now = datetime.now()
    if period == "Hoje":
        base_df = base_df[launched_series.dt.date == now.date()]
    elif period == "7 dias":
        base_df = base_df[launched_series >= now - timedelta(days=7)]
    elif period == "30 dias":
        base_df = base_df[launched_series >= now - timedelta(days=30)]

    if employee != "Todos":
        base_df = base_df[base_df["Responsável"] == employee]

    st.dataframe(base_df, width='stretch', hide_index=True)

    if not base_df.empty:
        launch_options = [None] + base_df["ID"].tolist()
        label_launch_id = st.selectbox("Gerar etiqueta novamente", launch_options)
        if label_launch_id is not None:
            launch = find_launch(label_launch_id)
            if launch is not None:
                render_label_actions(launch)

    if user["role"] == "admin" and not base_df.empty:
        ids = base_df["ID"].tolist()
        delete_id = st.selectbox("Excluir lançamento", [None] + ids)
        if delete_id and st.button("Excluir lançamento selecionado"):
            st.session_state.launches = [x for x in st.session_state.launches if x["id"] != delete_id]
            if st.session_state.last_label_launch_id == delete_id:
                st.session_state.last_label_launch_id = None
            st.success("Lançamento excluído.")
            st.rerun()


def render_products_admin() -> None:
    if st.button("Recarregar produtos do CSV", width='stretch'):
        sync_products_from_csv()
        st.success("Produtos recarregados do CSV.")
        st.rerun()

    st.subheader("Cadastro de produtos")
    st.caption(f"Banco em CSV na raiz do projeto: {PRODUCTS_CSV_PATH}")

    with st.form("product_form", clear_on_submit=True):
        name = st.text_input("Nome do produto")
        category = st.text_input("Categoria", value="Geral")
        shelf_life_days = st.number_input("Validade em dias", min_value=1, max_value=365, value=3)
        storage = st.selectbox("Armazenamento", ["Ambiente", "Refrigerado", "Congelado"])
        submitted = st.form_submit_button("Cadastrar produto")

    if submitted:
        if not name.strip():
            st.error("Informe o nome do produto.")
        else:
            st.session_state.products.append(
                {
                    "id": st.session_state.next_product_id,
                    "name": name.strip(),
                    "category": category.strip() or "Geral",
                    "shelf_life_days": int(shelf_life_days),
                    "storage": storage,
                    "active": True,
                }
            )
            persist_products()
            st.success("Produto cadastrado e salvo no CSV.")
            st.rerun()

    products_df = pd.DataFrame(
        [
            {
                "ID": p["id"],
                "Produto": p["name"],
                "Categoria": p["category"],
                "Validade (dias)": p["shelf_life_days"],
                "Armazenamento": p["storage"],
                "Ativo": "Sim" if p.get("active", True) else "Não",
            }
            for p in st.session_state.products
        ]
    )
    st.dataframe(products_df, width='stretch', hide_index=True)

    if st.session_state.products:
        st.markdown("### Editar produto")
        product_labels = {f"{p['name']} (ID {p['id']})": p["id"] for p in st.session_state.products}
        selected_label = st.selectbox("Produto para editar", list(product_labels.keys()))
        selected_product = find_product(product_labels[selected_label])

        if selected_product is not None:
            storage_options = ["Ambiente", "Refrigerado", "Congelado"]
            with st.form("edit_product_form"):
                edit_name = st.text_input("Nome", value=selected_product["name"])
                edit_category = st.text_input("Categoria", value=selected_product["category"])
                edit_shelf_life_days = st.number_input(
                    "Validade em dias",
                    min_value=1,
                    max_value=365,
                    value=int(selected_product["shelf_life_days"]),
                    key="edit_shelf_life_days",
                )
                edit_storage = st.selectbox(
                    "Armazenamento",
                    storage_options,
                    index=storage_options.index(selected_product["storage"]) if selected_product["storage"] in storage_options else 0,
                    key="edit_storage",
                )
                edit_active = st.checkbox("Produto ativo", value=bool(selected_product.get("active", True)))
                save_edit = st.form_submit_button("Atualizar produto")

            if save_edit:
                if not edit_name.strip():
                    st.error("Informe o nome do produto.")
                else:
                    selected_product["name"] = edit_name.strip()
                    selected_product["category"] = edit_category.strip() or "Geral"
                    selected_product["shelf_life_days"] = int(edit_shelf_life_days)
                    selected_product["storage"] = edit_storage
                    selected_product["active"] = bool(edit_active)
                    persist_products()
                    st.success("Produto atualizado no CSV.")
                    st.rerun()

        st.markdown("### Remover produto")
        delete_choice = st.selectbox("Produto para remover", [None] + list(product_labels.keys()), key="delete_product_choice")
        if delete_choice is not None and st.button("Remover produto", type="secondary"):
            product_id = product_labels[delete_choice]
            st.session_state.products = [product for product in st.session_state.products if product["id"] != product_id]
            persist_products()
            st.success("Produto removido do CSV.")
            st.rerun()

    csv_bytes = PRODUCTS_CSV_PATH.read_bytes() if PRODUCTS_CSV_PATH.exists() else b""
    st.download_button(
        "Baixar products.csv",
        data=csv_bytes,
        file_name="products.csv",
        mime="text/csv",
        width='stretch',
    )

    if PRODUCTS_CSV_PATH.exists():
        st.markdown("### CSV atual")
        st.code(PRODUCTS_CSV_PATH.read_text(encoding="utf-8-sig"), language="csv")




def main() -> None:
    configure_page()
    init_state()
    user = current_user()
    if not user:
        render_login()
        return


    st.text('oi')
    if user["role"] == "admin":
        tab1, tab2 = st.tabs(["Lançamento", "Produtos"])
        with tab1:
            render_quick_launch(user)
        with tab2:
            render_products_admin()

        # Histórico removido temporariamente da interface.
        # tab_hist = st.tabs(["Histórico"])
        # with tab_hist:
        #     render_history(user)
    else:
        render_quick_launch(user)

        # Histórico removido temporariamente da interface.
        # render_history(user)

    render_header(user)
    


if __name__ == "__main__":
    main()
