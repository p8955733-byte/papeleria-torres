import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import uuid
import os
import base64
import streamlit.components.v1 as components

# --- CONFIGURACIÓN BASE DE DATOS ---
DB_NAME = "papeleria_torres.db"
LOGO_PATH = "logo.jpeg"
STOCK_MINIMO = 5


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventario'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(inventario)")
            columnas = [col[1] for col in cursor.fetchall()]
            if 'imagen' not in columnas:
                try:
                    cursor.execute("ALTER TABLE inventario ADD COLUMN imagen TEXT DEFAULT ''")
                    conn.commit()
                except sqlite3.OperationalError:
                    pass
        else:
            cursor.execute('''CREATE TABLE inventario 
                              (producto TEXT, marca TEXT, categoria TEXT, presentacion TEXT, 
                               stock INTEGER, p_compra REAL, p_venta REAL, imagen TEXT,
                               PRIMARY KEY (producto, marca, categoria, presentacion))''')
            conn.commit()

        cursor.execute('''CREATE TABLE IF NOT EXISTS ventas 
                          (transaccion_id TEXT, fecha TEXT, hora TEXT, producto TEXT, marca TEXT, 
                           categoria TEXT, presentacion TEXT, cantidad INTEGER, p_venta REAL, total REAL, estado TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS apartados 
                          (id TEXT, cliente TEXT, fecha TEXT, producto TEXT, marca TEXT, 
                           categoria TEXT, presentacion TEXT, cantidad INTEGER, estado TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS compras 
                          (compra_id TEXT, fecha TEXT, hora TEXT, proveedor TEXT, producto TEXT, 
                           marca TEXT, categoria TEXT, presentacion TEXT, cantidad INTEGER, 
                           p_compra REAL, total REAL)''')
        conn.commit()


def run_query(query, params=()):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()


def get_df(query, params=()):
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_logo_base64():
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


def ejecutar_impresion(html_content, copias=1):
    unique_id = str(uuid.uuid4())[:8]
    component_script = f"""
    <div id="ticket-{unique_id}" style="display:none;">{html_content}</div>
    <script>
        (function() {{
            var content = document.getElementById('ticket-{unique_id}').innerHTML;
            var win = window.open('', 'PRINT', 'height=600,width=400');
            win.document.write('<html><head><title>Imprimir</title></head><body>' + content + '</body></html>');
            win.document.close();
            win.focus();
            for (var i = 0; i < {copias}; i++) {{ win.print(); }}
            win.close();
        }})();
    </script>
    """
    components.html(component_script, height=0)


@st.dialog("🖨️ Imprimir Ticket", width="large")
def mostrar_ventana_ticket(html_content, key_prefix=""):
    st.markdown("### Vista previa del ticket")
    components.html(html_content, height=420, scrolling=True)

    st.markdown("---")
    st.markdown("### Opciones de impresión")

    c1, c2 = st.columns(2)
    with c1:
        copias = st.number_input("Copias:", 1, 5, 1, key=f"copias_{key_prefix}")
    with c2:
        ancho_papel = st.selectbox(
            "Ancho del papel:",
            ["80mm (Estándar)", "58mm (Pequeño)", "A4 (Carta)"],
            key=f"ancho_{key_prefix}"
        )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🖨️ Imprimir", type="primary", use_container_width=True, key=f"print_{key_prefix}"):
            ejecutar_impresion(html_content, copias)
            st.success("✅ Enviado a impresión")
    with col2:
        if st.button("❌ Cerrar", use_container_width=True, key=f"cerrar_{key_prefix}"):
            st.session_state.ticket_reciente = None
            st.rerun()


def generar_ticket_html(titulo, id_doc, items, total, cliente=None, proveedor=None, tipo="venta"):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    logo_b64 = get_logo_base64()
    logo_html = f'<img src="data:image/jpeg;base64,{logo_b64}" style="width: 90px; margin-bottom: 5px;">' if logo_b64 else ''

    color = "#A78470"
    if tipo == "compra":
        color = "#5A7A9A"
    elif tipo == "apartado":
        color = "#9A7A5A"

    encabezado_extra = ""
    if cliente:
        encabezado_extra = f'<p style="font-size:11px;"><b>Cliente:</b> {cliente}</p>'
    elif proveedor:
        encabezado_extra = f'<p style="font-size:11px;"><b>Proveedor:</b> {proveedor}</p>'

    filas = ""
    for it in items:
        filas += f"<tr><td>{it.get('marca', '')} {it['producto']}<br><small>{it.get('presentacion', '')}</small></td><td align='center'>{it['cantidad']}</td><td align='right'>${it['subtotal']:,.2f}</td></tr>"

    return f"""
    <div style="font-family: 'Courier New', monospace; width: 250px; padding: 10px; background: white; color: black; border: 1px solid #ddd; margin: 0 auto;">
        <center>
            {logo_html}
            <h2 style="margin:0; color:{color};">PAPELERÍA TORRES</h2>
            <p style="font-size:12px; margin:0;">{titulo}</p>
        </center>
        <hr>
        <p style="font-size:11px;"><b>No.</b> #{id_doc}<br><b>Fecha:</b> {fecha}</p>
        {encabezado_extra}
        <table style="width:100%; font-size:10px;">
            {filas}
        </table>
        <hr><h3 align="right" style="color:{color};">TOTAL: ${total:,.2f}</h3>
        <p style="font-size:9px; text-align:center;">¡Gracias por su preferencia!</p>
        <p style="font-size:8px; text-align:center; color:#B89A86;">Papelería Torres ❤️</p>
    </div>
    """


def mostrar_alertas_stock():
    df_bajo = get_df(
        f"SELECT producto, marca, presentacion, stock FROM inventario WHERE stock <= {STOCK_MINIMO} ORDER BY stock ASC")
    if not df_bajo.empty:
        st.error(f"🚨 **¡ALERTA!** Hay **{len(df_bajo)}** producto(s) con stock bajo (≤ {STOCK_MINIMO} unidades):")
        for _, row in df_bajo.iterrows():
            if row['stock'] == 0:
                st.markdown(f"🔴 **{row['producto']}** - {row['marca']} ({row['presentacion']}): **AGOTADO**")
            elif row['stock'] <= 2:
                st.markdown(
                    f"🟠 **{row['producto']}** - {row['marca']} ({row['presentacion']}): **{row['stock']} unidades**")
            else:
                st.markdown(
                    f"🟡 **{row['producto']}** - {row['marca']} ({row['presentacion']}): **{row['stock']} unidades**")
        st.markdown("---")
    return df_bajo


# --- INICIALIZACIÓN ---
st.set_page_config(page_title="Papelería Torres - Sistema de Ventas", page_icon="📚", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F4EFE9; }
    [data-testid="stSidebar"] { background-color: #C9B6A8; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    [data-testid="stSidebar"] img {
        background-color: #F4EFE9; border-radius: 50%; padding: 8px;
        border: 4px solid #A78470; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        display: block; margin: 10px auto;
    }
    h1, h2, h3 { color: #A78470 !important; }
    .stButton > button[kind="primary"] { background-color: #A78470; color: #FFFFFF; border: none; border-radius: 8px; font-weight: bold; }
    .stButton > button[kind="primary"]:hover { background-color: #B89A86; color: #FFFFFF; }
    .stButton > button[kind="secondary"] { background-color: #E8DCCF; color: #A78470; border: 1px solid #B89A86; border-radius: 8px; }
    .stButton > button[kind="secondary"]:hover { background-color: #C9B6A8; color: #FFFFFF; }
    .stButton > button { background-color: #B89A86; color: #FFFFFF; border-radius: 8px; border: none; }
    .stButton > button:hover { background-color: #A78470; color: #FFFFFF; }
    [data-testid="stMetric"] { background-color: #E8DCCF; border: 2px solid #B89A86; border-radius: 10px; padding: 15px; }
    [data-testid="stMetricLabel"] { color: #A78470 !important; font-weight: bold; }
    [data-testid="stMetricValue"] { color: #A78470 !important; }
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #FFFFFF !important; border: 1px solid #B89A86 !important; border-radius: 6px;
    }
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] { border: 2px solid #B89A86; border-radius: 8px; overflow: hidden; }
    .stAlert { background-color: #E8DCCF; color: #A78470; border-left: 5px solid #A78470; }
    [data-testid="stForm"] { background-color: #E8DCCF; border: 2px solid #B89A86; border-radius: 10px; padding: 20px; }
</style>
""", unsafe_allow_html=True)

init_db()

if 'carrito' not in st.session_state:
    st.session_state.carrito = []
if 'ticket_reciente' not in st.session_state:
    st.session_state.ticket_reciente = None

try:
    st.sidebar.image(LOGO_PATH, use_container_width=True)
except Exception:
    st.sidebar.markdown("## 📚 PAPELERÍA TORRES")

st.sidebar.markdown("""
    <div style='text-align: center; padding: 5px 0 15px 0;'>
        <h2 style='color: white; margin: 0; font-size: 20px;'>PAPELERÍA TORRES</h2>
        <p style='color: #F4EFE9; font-size: 12px; margin: 0;'>Sistema de Ventas</p>
    </div>
""", unsafe_allow_html=True)

df_alerta_sidebar = get_df(f"SELECT COUNT(*) as n FROM inventario WHERE stock <= {STOCK_MINIMO}")
n_alertas = df_alerta_sidebar['n'].iloc[0] if not df_alerta_sidebar.empty else 0
if n_alertas > 0:
    st.sidebar.warning(f"🚨 {n_alertas} producto(s) con stock bajo")

st.sidebar.markdown("---")

menu = ["📦 Inventario", "🛒 Punto de Venta", "🧾 Compras", "📝 Apartados",
        "📊 Corte de Caja", "📉 Historial", "🛠️ Admin", "💾 Respaldos"]
choice = st.sidebar.selectbox("Opciones", menu)

col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
with col_l2:
    try:
        st.image(LOGO_PATH, width=180)
    except Exception:
        pass

df_alerta_global = get_df(f"SELECT COUNT(*) as n FROM inventario WHERE stock <= {STOCK_MINIMO}")
if not df_alerta_global.empty and df_alerta_global['n'].iloc[0] > 0:
    st.warning(
        f"🚨 **Alerta:** Hay **{df_alerta_global['n'].iloc[0]}** producto(s) con stock bajo (≤ {STOCK_MINIMO} unidades). Revisa la sección **📦 Inventario**.")

# --- 1. INVENTARIO ---
if choice == "📦 Inventario":
    st.header("📦 Inventario de Productos")
    mostrar_alertas_stock()

    df_inv = get_df("SELECT * FROM inventario")
    if not df_inv.empty:
        def resaltar_stock(row):
            if row['stock'] == 0:
                return ['background-color: #FFCCCC'] * len(row)
            elif row['stock'] <= STOCK_MINIMO:
                return ['background-color: #FFE5CC'] * len(row)
            return [''] * len(row)


        st.dataframe(df_inv.style.apply(resaltar_stock, axis=1), width='stretch')
    else:
        st.info("No hay productos en el inventario.")

# --- 2. PUNTO DE VENTA ---
elif choice == "🛒 Punto de Venta":
    st.header("🛒 Nueva Venta")
    df_inv = get_df("SELECT * FROM inventario WHERE stock > 0")

    if not df_inv.empty:
        c1, c2 = st.columns(2)
        with c1:
            marca_sel = st.selectbox("Marca", sorted(df_inv['marca'].unique()))
            df_f = df_inv[df_inv['marca'] == marca_sel]
            prod_sel = st.selectbox("Producto", sorted(df_f['producto'].unique()))
            df_f = df_f[df_f['producto'] == prod_sel]
            cat_sel = st.selectbox("Categoría", sorted(df_f['categoria'].unique()))
            df_f = df_f[df_f['categoria'] == cat_sel]
            pres_sel = st.selectbox("Presentación", sorted(df_f['presentacion'].unique()))
            item = df_f[df_f['presentacion'] == pres_sel].iloc[0]

            if item['stock'] <= STOCK_MINIMO:
                st.warning(f"⚠️ Stock bajo: solo quedan {item['stock']} unidades")

            st.info(f"Stock: {item['stock']} | Precio: ${item['p_venta']:,.2f}")
            cant = st.number_input("Cantidad", 1, int(item['stock']))

            if st.button("➕ Agregar al Carrito", use_container_width=True):
                st.session_state.carrito.append({
                    'producto': item['producto'], 'marca': item['marca'], 'categoria': item['categoria'],
                    'presentacion': item['presentacion'], 'cantidad': cant, 'precio': item['p_venta'],
                    'subtotal': item['p_venta'] * cant
                })
                st.rerun()

            if st.button("🗑️ Limpiar Todo", type="secondary", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()

        with c2:
            if st.session_state.carrito:
                st.subheader("🧾 Resumen de Venta")
                st.table(pd.DataFrame(st.session_state.carrito)[
                             ['producto', 'marca', 'presentacion', 'cantidad', 'subtotal']])
                total_v = sum(i['subtotal'] for i in st.session_state.carrito)
                if st.button(f"✅ Finalizar e Imprimir (${total_v:,.2f})", type="primary", use_container_width=True):
                    t_id = str(uuid.uuid4())[:8].upper()
                    now = datetime.now()
                    carrito_actual = st.session_state.carrito.copy()
                    for i in carrito_actual:
                        run_query("INSERT INTO ventas VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                  (t_id, now.strftime("%Y-%m-%d"), now.strftime("%H:%M"),
                                   i['producto'], i['marca'], i['categoria'], i['presentacion'],
                                   i['cantidad'], i['precio'], i['subtotal'], "COMPLETADA"))
                        run_query(
                            "UPDATE inventario SET stock = stock - ? WHERE producto=? AND marca=? AND categoria=? AND presentacion=?",
                            (i['cantidad'], i['producto'], i['marca'], i['categoria'], i['presentacion']))

                    st.session_state.ticket_reciente = generar_ticket_html(
                        "TICKET VENTA", t_id, carrito_actual, total_v, tipo="venta"
                    )
                    st.session_state.carrito = []
                    st.rerun()

    if st.session_state.get('ticket_reciente'):
        mostrar_ventana_ticket(st.session_state.ticket_reciente, key_prefix="venta")

# --- 3. COMPRAS ---
elif choice == "🧾 Compras":
    st.header("🧾 Registro de Compras a Proveedores")
    st.markdown("Registra entradas de mercancía. Se sumará automáticamente al inventario.")

    df_inv = get_df("SELECT * FROM inventario")

    with st.form("form_compra"):
        c1, c2 = st.columns(2)
        with c1:
            proveedor = st.text_input("Proveedor", placeholder="Ej: Distribuidora Escolar SA")
            usar_existente = st.checkbox("Producto ya existe en inventario", value=True)

            prod = marca = cat = pres = ""
            if usar_existente and not df_inv.empty:
                df_inv['lbl'] = df_inv['producto'] + " | " + df_inv['marca'] + " (" + df_inv['presentacion'] + ")"
                prod_sel = st.selectbox("Producto existente", df_inv['lbl'])
                r = df_inv[df_inv['lbl'] == prod_sel].iloc[0]
                prod = r['producto'];
                marca = r['marca'];
                cat = r['categoria'];
                pres = r['presentacion']
                st.info(f"Producto actual → Stock: {r['stock']} | Costo: ${r['p_compra']:,.2f}")
            else:
                prod = st.text_input("Producto nuevo")
                marca = st.text_input("Marca")
                cat = st.text_input("Categoría")
                pres = st.text_input("Presentación")
        with c2:
            cant = st.number_input("Cantidad comprada", 1, step=1)
            p_compra = st.number_input("Precio de compra unitario", 0.0, step=0.5)
            p_venta_sugerido = st.number_input("Precio de venta (si es nuevo)", 0.0, step=0.5)

        submitted = st.form_submit_button("💾 Registrar Compra", type="primary", use_container_width=True)

    if submitted:
        if prod and marca and cat and pres:
            c_id = "C-" + str(uuid.uuid4())[:6].upper()
            now = datetime.now()
            total_compra = cant * p_compra

            existe = get_df("SELECT * FROM inventario WHERE producto=? AND marca=? AND categoria=? AND presentacion=?",
                            (prod, marca, cat, pres))
            if not existe.empty:
                nuevo_stock = int(existe['stock'].iloc[0]) + cant
                run_query(
                    "UPDATE inventario SET stock=?, p_compra=? WHERE producto=? AND marca=? AND categoria=? AND presentacion=?",
                    (nuevo_stock, p_compra, prod, marca, cat, pres))
            else:
                run_query("""INSERT INTO inventario 
                             (producto, marca, categoria, presentacion, stock, p_compra, p_venta, imagen) 
                             VALUES (?,?,?,?,?,?,?,?)""",
                          (prod, marca, cat, pres, cant, p_compra, p_venta_sugerido, ""))

            run_query("INSERT INTO compras VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (c_id, now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), proveedor,
                       prod, marca, cat, pres, cant, p_compra, total_compra))

            item_compra = [{'producto': prod, 'marca': marca, 'presentacion': pres,
                            'cantidad': cant, 'subtotal': total_compra}]
            st.session_state.ticket_reciente = generar_ticket_html(
                "TICKET COMPRA", c_id, item_compra, total_compra,
                proveedor=proveedor, tipo="compra"
            )
            st.rerun()
        else:
            st.error("Completa todos los campos del producto.")

    if st.session_state.get('ticket_reciente'):
        mostrar_ventana_ticket(st.session_state.ticket_reciente, key_prefix="compra")

    st.markdown("---")
    st.subheader("📜 Compras Recientes")
    df_compras = get_df("SELECT * FROM compras ORDER BY fecha DESC, hora DESC LIMIT 20")
    if not df_compras.empty:
        st.dataframe(df_compras, width='stretch')
    else:
        st.info("No hay compras registradas.")

# --- 4. APARTADOS ---
elif choice == "📝 Apartados":
    st.header("📝 Control de Apartados")
    df_inv = get_df("SELECT * FROM inventario WHERE stock > 0")

    if df_inv.empty:
        st.info("No hay productos con stock disponible.")
    else:
        with st.form("ap_f"):
            cli = st.text_input("Nombre del Cliente")
            df_inv['lbl'] = df_inv['producto'] + " | " + df_inv['marca'] + " (" + df_inv['presentacion'] + ")"
            sel = st.selectbox("Producto", df_inv['lbl'])
            cnt = st.number_input("Cantidad", 1)
            submitted = st.form_submit_button("Guardar Apartado")

        if submitted:
            r = df_inv[df_inv['lbl'] == sel].iloc[0]
            ap_id = "AP-" + str(uuid.uuid4())[:4].upper()
            run_query("INSERT INTO apartados VALUES (?,?,?,?,?,?,?,?,?)",
                      (ap_id, cli, datetime.now().strftime("%Y-%m-%d"), r['producto'], r['marca'],
                       r['categoria'], r['presentacion'], cnt, "ACTIVO"))
            run_query(
                "UPDATE inventario SET stock = stock - ? WHERE producto=? AND marca=? AND categoria=? AND presentacion=?",
                (cnt, r['producto'], r['marca'], r['categoria'], r['presentacion']))

            st.session_state.ticket_reciente = generar_ticket_html(
                "VALE APARTADO", ap_id,
                [{'producto': r['producto'], 'marca': r['marca'], 'presentacion': r['presentacion'],
                  'cantidad': cnt, 'subtotal': r['p_venta'] * cnt}],
                r['p_venta'] * cnt, cliente=cli, tipo="apartado"
            )
            st.rerun()

        if st.session_state.get('ticket_reciente'):
            mostrar_ventana_ticket(st.session_state.ticket_reciente, key_prefix="apartado")

# --- 5. CORTE DE CAJA ---
elif choice == "📊 Corte de Caja":
    st.header("📊 Corte de Caja y Utilidades")
    periodo = st.radio("Seleccione Periodo de Corte:", ["Hoy", "Esta Semana", "Este Mes"], horizontal=True)

    hoy = datetime.now()
    if periodo == "Hoy":
        fecha_inicio = hoy.strftime("%Y-%m-%d")
    elif periodo == "Esta Semana":
        fecha_inicio = (hoy - timedelta(days=hoy.weekday())).strftime("%Y-%m-%d")
    else:
        fecha_inicio = hoy.strftime("%Y-%m-01")

    query_corte = """
        SELECT v.*, i.p_compra 
        FROM ventas v 
        LEFT JOIN inventario i ON v.producto = i.producto AND v.marca = i.marca AND v.categoria = i.categoria AND v.presentacion = i.presentacion
        WHERE v.fecha >= ? AND v.estado = 'COMPLETADA'
    """
    df_corte = get_df(query_corte, (fecha_inicio,))

    if not df_corte.empty:
        total_ventas = df_corte['total'].sum()
        total_costos = (df_corte['cantidad'] * df_corte['p_compra'].fillna(0)).sum()
        utilidad = total_ventas - total_costos

        m1, m2, m3 = st.columns(3)
        m1.metric("Ingresos Totales", f"${total_ventas:,.2f}")
        m2.metric("Inversión (Costos)", f"${total_costos:,.2f}")
        m3.metric("Utilidad Neta", f"${utilidad:,.2f}",
                  delta=f"{(utilidad / total_ventas) * 100:.1f}%" if total_ventas > 0 else "0%")

        st.subheader("Detalle de Ventas en el Periodo")
        st.dataframe(df_corte[['transaccion_id', 'fecha', 'producto', 'marca', 'presentacion', 'cantidad', 'total']],
                     width='stretch')
    else:
        st.info(f"No hay ventas registradas desde el {fecha_inicio}")

# --- 6. HISTORIAL ---
elif choice == "📉 Historial":
    st.header("📉 Historial de Operaciones")

    tab1, tab2, tab3 = st.tabs(["🛒 Ventas", "📝 Apartados", "🧾 Compras"])
    with tab1:
        st.dataframe(get_df("SELECT * FROM ventas"), width='stretch')
    with tab2:
        st.dataframe(get_df("SELECT * FROM apartados"), width='stretch')
    with tab3:
        st.dataframe(get_df("SELECT * FROM compras"), width='stretch')

# --- 7. ADMIN ---
elif choice == "🛠️ Admin":
    st.header("🛠️ Administración de Inventario")

    tab1, tab2 = st.tabs([
        "🔍 Buscar / Filtrar / Editar",
        "🗑️ Eliminar"
    ])

    # ============================================================
    # TAB 1: BUSCAR / FILTRAR / EDITAR (Método Infalible)
    # ============================================================
    with tab1:
        st.subheader("🔍 Búsqueda Avanzada y Edición de Productos")

        st.info(
            "💡 **¿Cómo editar?** 1. Haz **doble clic** en el número de **Stock** o **Precios**. 2. Cambia el valor y presiona **Enter**. 3. Escribe el nombre del producto en el cuadro de abajo y presiona **Guardar Cambios**.")

        df_base = get_df("SELECT * FROM inventario")

        if df_base.empty:
            st.warning("⚠️ No hay productos en el inventario.")
        else:
            # --- Filtros principales ---
            st.markdown("### 🎯 Filtros principales")
            f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
            with f1:
                txt_producto = st.text_input(
                    "🔎 Producto (nombre)",
                    placeholder="Escribe parte del nombre..."
                )
            with f2:
                f_categoria = st.selectbox(
                    "📂 Categoría",
                    ["Todas"] + sorted(df_base['categoria'].dropna().unique().tolist())
                )
            with f3:
                f_marca = st.selectbox(
                    "🏷️ Marca",
                    ["Todas"] + sorted(df_base['marca'].dropna().unique().tolist())
                )
            with f4:
                f_stock_bajo = st.checkbox(
                    f"🚨 Solo stock bajo (≤ {STOCK_MINIMO})",
                    value=False
                )

            st.markdown("### ⚙️ Filtros adicionales")

            g1, g2, g3 = st.columns(3)
            with g1:
                f_presentacion = st.selectbox(
                    "📏 Presentación",
                    ["Todas"] + sorted(df_base['presentacion'].dropna().unique().tolist())
                )
            with g2:
                f_estado_stock = st.selectbox(
                    "📊 Estado de stock",
                    ["Todos", "Agotado (=0)", "Bajo (≤ umbral)", "Normal (> umbral)"]
                )
            with g3:
                f_orden = st.selectbox(
                    "🔀 Ordenar por",
                    ["Producto (A-Z)", "Producto (Z-A)", "Stock (menor→mayor)",
                     "Stock (mayor→menor)", "Precio venta (menor→mayor)",
                     "Precio venta (mayor→menor)", "Precio compra (menor→mayor)",
                     "Precio compra (mayor→menor)"]
                )

            # Forzamos que los máximos SIEMPRE tengan un valor válido (nunca 0)
            max_stock = int(df_base['stock'].max()) if not df_base.empty and int(df_base['stock'].max()) > 0 else 1000
            max_pv = float(df_base['p_venta'].max()) if not df_base.empty and float(
                df_base['p_venta'].max()) > 0 else 1000.0
            max_pc = float(df_base['p_compra'].max()) if not df_base.empty and float(
                df_base['p_compra'].max()) > 0 else 1000.0

            g4, g5 = st.columns(2)
            with g4:
                st.markdown("**Rango de stock**")
                c1s, c2s = st.columns(2)
                stock_min = c1s.number_input(
                    "Mín", min_value=0, value=0, step=1,
                    key="filtro_stock_min_v3"
                )
                stock_max = c2s.number_input(
                    "Máx", min_value=0, value=max_stock, step=1,
                    key="filtro_stock_max_v3"
                )
            with g5:
                st.markdown("**Rango de precio de venta**")
                c1p, c2p = st.columns(2)
                pv_min = c1p.number_input(
                    "Mín $", min_value=0.0, value=0.0,
                    step=0.5, key="filtro_pv_min_v3"
                )
                pv_max = c2p.number_input(
                    "Máx $", min_value=0.0, value=max_pv,
                    step=0.5, key="filtro_pv_max_v3"
                )

            st.markdown("**Rango de precio de compra**")
            c1c, c2c = st.columns(2)
            pc_min = c1c.number_input(
                "Mín $", min_value=0.0, value=0.0,
                step=0.5, key="filtro_pc_min_v3"
            )
            pc_max = c2c.number_input(
                "Máx $", min_value=0.0, value=max_pc,
                step=0.5, key="filtro_pc_max_v3"
            )

            # --- Aplicar filtros ---
            df_f = df_base.copy()

            if txt_producto.strip():
                df_f = df_f[df_f['producto'].str.contains(
                    txt_producto.strip(), case=False, na=False
                )]

            if f_categoria != "Todas":
                df_f = df_f[df_f['categoria'] == f_categoria]

            if f_marca != "Todas":
                df_f = df_f[df_f['marca'] == f_marca]

            if f_presentacion != "Todas":
                df_f = df_f[df_f['presentacion'] == f_presentacion]

            if f_stock_bajo:
                df_f = df_f[df_f['stock'] <= STOCK_MINIMO]

            if f_estado_stock == "Agotado (=0)":
                df_f = df_f[df_f['stock'] == 0]
            elif f_estado_stock == "Bajo (≤ umbral)":
                df_f = df_f[(df_f['stock'] > 0) & (df_f['stock'] <= STOCK_MINIMO)]
            elif f_estado_stock == "Normal (> umbral)":
                df_f = df_f[df_f['stock'] > STOCK_MINIMO]

            df_f = df_f[
                (df_f['stock'] >= stock_min) & (df_f['stock'] <= stock_max) &
                (df_f['p_venta'] >= pv_min) & (df_f['p_venta'] <= pv_max) &
                (df_f['p_compra'] >= pc_min) & (df_f['p_compra'] <= pc_max)
                ]

            orden_map = {
                "Producto (A-Z)": ('producto', True),
                "Producto (Z-A)": ('producto', False),
                "Stock (menor→mayor)": ('stock', True),
                "Stock (mayor→menor)": ('stock', False),
                "Precio venta (menor→mayor)": ('p_venta', True),
                "Precio venta (mayor→menor)": ('p_venta', False),
                "Precio compra (menor→mayor)": ('p_compra', True),
                "Precio compra (mayor→menor)": ('p_compra', False),
            }
            col_orden, asc = orden_map[f_orden]
            df_f = df_f.sort_values(by=col_orden, ascending=asc).reset_index(drop=True)

            # --- Resumen ---
            st.markdown("---")
            r1, r2, r3 = st.columns(3)
            r1.metric("🔢 Resultados", len(df_f))
            r2.metric("📦 Stock total", int(df_f['stock'].sum()) if not df_f.empty else 0)
            r3.metric(
                "💰 Valor inventario (venta)",
                f"${(df_f['stock'] * df_f['p_venta']).sum():,.2f}" if not df_f.empty else "$0.00"
            )

            # --- Tabla EDITABLE ---
            if not df_f.empty:
                st.markdown("### ✏️ Tabla editable (Modifica las celdas aquí abajo)")

                cols_mostrar = ['producto', 'marca', 'categoria', 'presentacion',
                                'stock', 'p_compra', 'p_venta']
                df_editable = df_f[cols_mostrar].reset_index(drop=True)

                # Añadimos un ID temporal oculto para no perder el rastro
                df_editable.insert(0, 'id_oculto', range(len(df_editable)))

                df_editado = st.data_editor(
                    df_editable,
                    width='stretch',
                    hide_index=True,
                    num_rows="fixed",
                    key="editor_inventario_v3",
                    column_config={
                        "id_oculto": None,  # Ocultamos esta columna
                        "producto": st.column_config.TextColumn(
                            "Producto", disabled=True, width="medium"
                        ),
                        "marca": st.column_config.TextColumn(
                            "Marca", disabled=True, width="small"
                        ),
                        "categoria": st.column_config.TextColumn(
                            "Categoría", disabled=True, width="small"
                        ),
                        "presentacion": st.column_config.TextColumn(
                            "Presentación", disabled=True, width="small"
                        ),
                        "stock": st.column_config.NumberColumn(
                            "Stock", min_value=0, step=1, format="%d", width="small"
                        ),
                        "p_compra": st.column_config.NumberColumn(
                            "P. Compra", min_value=0.0, step=0.5, format="$%.2f", width="small"
                        ),
                        "p_venta": st.column_config.NumberColumn(
                            "P. Venta", min_value=0.0, step=0.5, format="$%.2f", width="small"
                        ),
                    }
                )

                # --- MÉTODO INFALIBLE DE GUARDADO ---
                st.markdown("---")
                st.markdown("#### 💾 Confirmar Cambios")
                st.markdown("Escribe el **nombre exacto** del producto que acabas de editar y presiona Guardar.")

                col_conf1, col_conf2 = st.columns([2, 1])
                with col_conf1:
                    nombre_confirmar = st.text_input("Nombre del producto editado:", placeholder="Ej. Abaco chico",
                                                     key="input_guardar")
                with col_conf2:
                    st.markdown("<br>", unsafe_allow_html=True)  # Espacio para alinear el botón
                    btn_guardar = st.button("💾 Guardar Cambios", type="primary", use_container_width=True)

                if btn_guardar:
                    if nombre_confirmar.strip() == "":
                        st.error("⚠️ Debes escribir el nombre del producto para confirmar.")
                    else:
                        # Buscar la fila en la tabla editada
                        fila = df_editado[df_editado['producto'].str.lower() == nombre_confirmar.strip().lower()]

                        if fila.empty:
                            st.error(
                                f"❌ No se encontró el producto '{nombre_confirmar}' en la tabla actual. Verifica el nombre.")
                        else:
                            r = fila.iloc[0]
                            # Actualizar en la base de datos
                            run_query(
                                """UPDATE inventario 
                                   SET stock=?, p_compra=?, p_venta=? 
                                   WHERE producto=? AND marca=? AND categoria=? AND presentacion=?""",
                                (int(r['stock']), float(r['p_compra']), float(r['p_venta']),
                                 r['producto'], r['marca'], r['categoria'], r['presentacion'])
                            )
                            st.success(f"✅ Producto **{r['producto']}** actualizado correctamente.")
                            st.rerun()

                # --- Exportar resultados ---
                csv = df_editado.drop(columns=['id_oculto']).to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Exportar resultados a CSV",
                    csv,
                    f"inventario_filtrado_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ Ningún producto coincide con los filtros aplicados. Ajusta los criterios.")

        # --- Agregar producto nuevo (dentro de la misma pestaña) ---
        st.markdown("---")
        with st.expander("➕ Agregar producto nuevo al inventario"):
            with st.form("adm_nuevo_v3"):
                c1, c2, c3, c4 = st.columns(4)
                p = c1.text_input("Producto (ej. Cuaderno)")
                m = c2.text_input("Marca (ej. Scribe)")
                col = c3.text_input("Categoría (ej. Escolar)")
                t = c4.text_input("Presentación (ej. 100 hojas)")
                s = st.number_input("Stock", 0)
                pc, pv = st.number_input("Precio Compra", 0.0), st.number_input("Precio Venta", 0.0)
                submitted = st.form_submit_button("Guardar en Inventario", type="primary")

            if submitted:
                if p and m and col and t:
                    run_query("""INSERT OR REPLACE INTO inventario 
                                 (producto, marca, categoria, presentacion, stock, p_compra, p_venta, imagen) 
                                 VALUES (?,?,?,?,?,?,?,?)""",
                              (p, m, col, t, s, pc, pv, ""))
                    if s <= STOCK_MINIMO:
                        st.warning(f"⚠️ Este producto tiene stock bajo ({s} unidades).")
                    st.success("Producto guardado exitosamente.")
                    st.rerun()
                else:
                    st.error("Completa todos los campos.")

    # ============================================================
    # TAB 2: ELIMINAR
    # ============================================================
    with tab2:
        st.subheader("🗑️ Eliminar Producto")
        df_all = get_df("SELECT * FROM inventario")
        if not df_all.empty:
            df_all['lbl'] = df_all['producto'] + " | " + df_all['marca'] + " | " + df_all['presentacion']
            sel_del = st.selectbox("Producto a eliminar:", df_all['lbl'])
            if st.button("🗑️ Eliminar Definitivamente", type="primary"):
                r = df_all[df_all['lbl'] == sel_del].iloc[0]
                run_query("DELETE FROM inventario WHERE producto=? AND marca=? AND categoria=? AND presentacion=?",
                          (r['producto'], r['marca'], r['categoria'], r['presentacion']))
                st.success("Producto eliminado.")
                st.rerun()
        else:
            st.info("No hay productos en el inventario.")

# --- 8. RESPALDOS ---
elif choice == "💾 Respaldos":
    st.header("💾 Respaldos del Sistema")
    if os.path.exists(DB_NAME):
        with open(DB_NAME, "rb") as f:
            st.download_button("📥 Descargar Base de Datos", f,
                               f"Backup_PapeleriaTorres_{datetime.now().strftime('%Y%m%d')}.db")

    file_up = st.file_uploader("Restaurar Base de Datos", type=["db"])
    if file_up and st.button("🚀 Restaurar"):
        with open(DB_NAME, "wb") as f:
            f.write(file_up.getbuffer())
        st.rerun()