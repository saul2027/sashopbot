import io
import time
import hmac
import hashlib
import psycopg2
import requests
import os
from threading import Thread
from flask import Flask
from urllib.parse import urlencode
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeChat

# =====================================================================
# 🔴 ZONA DE REEMPLAZO: TUS CREDENCIALES 🔴
# =====================================================================
TELEGRAM_TOKEN = "9085229716:AAHYsLL2wmOwYJGweQACxLv5jp5ltiQLnXI"
ADMIN_ID = 8499104949
ADMIN_USERNAME = "uservipxd"
BINANCE_PAY_ID = "884195829"
BINANCE_API_KEY = "NCztoP5SVCX71cehqZeKTdEOntTGpYDRw3M0NNpSEgxFifgtiMErhbsSIcnVn4TW"
BINANCE_SECRET_KEY = "31skkrCvejqUclA2tn5A5gprMZ3t8HvfVn1FTKYZvpn5eqUbEyG2de5ftR5oW4tL"

# Tu enlace de Supabase (Reemplaza [YOUR-PASSWORD] por tu contraseña real)
DATABASE_URL = "postgresql://postgres:saul20262026202@db.lckxsqdgmawjytbnzqab.supabase.co:5432/postgres"

CATALOGO_INICIAL = {
    "Gemini Pro": (3.00, "Cuenta completa email:pass"),
    "ChatGPT Plus": (4.50, "Cuenta completa email:pass"),
    "Netflix Completa": (6.50, "Perfil o pantalla email:pass"),
    "Disney+ Completa": (4.00, "Cuenta completa email:pass"),
    "Max Completa": (3.50, "Cuenta completa email:pass"),
    "Prime Video Completa": (3.00, "Cuenta completa email:pass"),
    "Spotify Individual": (2.00, "Invitación o cuenta email:pass"),
    "Crunchyroll Mega Fan": (2.50, "Cuenta completa email:pass"),
    "Canva Pro": (1.50, "Activación directa a tu correo")
}

# =====================================================================
# 🌐 MINI SERVIDOR WEB PARA 24/7 (RENDER / KOYEB) 🌐
# =====================================================================
app = Flask('')

@app.route('/')
def home():
    return "¡Bot SA SHOP Pro 24/7 con Supabase activo!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# =====================================================================
# ⚙️ MOTOR DEL BOT Y CONEXIÓN A SUPABASE ⚙️
# =====================================================================
bot = telebot.TeleBot(TELEGRAM_TOKEN)

compras_pendientes = {}
estado_carga_admin = {}
estado_precio_admin = {}
estado_mod_nombre = {}
estado_mod_desc = {}
estado_agregar_plat = {}
esperando_ticket_soporte = set()
estado_notificacion_admin = {}
esperando_noti_global = set()

def get_db():
    return psycopg2.connect("postgresql://postgres.lckxsqdgmawjytbnzqab:saul20262026202@aws-0-us-east-1.pooler.supabase.com:6543/postgres")

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    nombre TEXT,
                    compras INTEGER DEFAULT 0,
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS stock (
                    id SERIAL PRIMARY KEY,
                    producto TEXT,
                    credenciales TEXT,
                    vendido INTEGER DEFAULT 0
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS pagos_usados (
                    order_id TEXT PRIMARY KEY,
                    user_id BIGINT,
                    monto REAL,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS historial_compras (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    producto TEXT,
                    credenciales TEXT,
                    precio REAL,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS catalogo_db (
                    producto TEXT PRIMARY KEY,
                    precio REAL,
                    descripcion TEXT
                )""")
    
    c.execute("SELECT COUNT(*) FROM catalogo_db")
    if c.fetchone()[0] == 0:
        for prod, (precio, desc) in CATALOGO_INICIAL.items():
            c.execute("INSERT INTO catalogo_db (producto, precio, descripcion) VALUES (%s, %s, %s) ON CONFLICT (producto) DO NOTHING", (prod, precio, desc))

    conn.commit()
    c.close()
    conn.close()

init_db()

def obtener_catalogo():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT producto, precio, descripcion FROM catalogo_db")
    filas = c.fetchall()
    c.close()
    conn.close()
    return {prod: {"precio": prec, "desc": desc} for prod, prec, desc in filas}

def obtener_precio(producto):
    cat = obtener_catalogo()
    if producto in cat:
        return cat[producto]["precio"]
    return 0.0

def es_producto_a_correo(producto):
    cat = obtener_catalogo()
    if producto in cat:
        desc = cat[producto]["desc"].lower()
        return "correo" in desc or "activación" in desc
    return False

def configurar_menu_comandos():
    try:
        comandos_publicos = [
            BotCommand("menu", "🏠 Menú Principal"),
            BotCommand("buy", "🛒 Catálogo de Compras"),
            BotCommand("stock", "📊 Consultar Stock")
        ]
        bot.set_my_commands(comandos_publicos)

        comandos_admin = comandos_publicos + [
            BotCommand("cmds", "👑 Panel de Administración"),
            BotCommand("cargar", "📥 Subir Stock"),
            BotCommand("agregar_plataforma", "➕ Agregar plataforma"),
            BotCommand("quitar_plataforma", "🗑️ Eliminar plataforma"),
            BotCommand("modificar_nombre", "✏️ Cambiar nombre"),
            BotCommand("modificar_precio", "💵 Cambiar precio"),
            BotCommand("modificar_descripcion", "📌 Cambiar descripción"),
            BotCommand("noti", "📢 Anuncio Global"),
            BotCommand("stats", "📈 Estadísticas")
        ]
        bot.set_my_commands(comandos_admin, scope=BotCommandScopeChat(ADMIN_ID))
    except Exception:
        pass

configurar_menu_comandos()

def registrar_o_actualizar_usuario(user):
    conn = get_db()
    c = conn.cursor()
    uname = user.username.lower() if user.username else ""
    nombre = user.first_name or "Usuario"
    c.execute("INSERT INTO usuarios (user_id, username, nombre, compras) VALUES (%s, %s, %s, 0) ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username, nombre = EXCLUDED.nombre",
              (user.id, uname, nombre))
    conn.commit()
    c.close()
    conn.close()

def obtener_datos_usuario(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, nombre, compras FROM usuarios WHERE user_id = %s", (user_id,))
    fila = c.fetchone()
    c.close()
    conn.close()
    if not fila:
        return user_id, "Sin @username", "Cliente", 0
    return fila[0], (f"@{fila[1]}" if fila[1] else "Sin @username"), (fila[2] or "Cliente"), (fila[3] or 0)

def buscar_id_por_id_o_username(identificador):
    limpio = identificador.strip().lstrip("@").lower()
    conn = get_db()
    c = conn.cursor()
    if limpio.isdigit():
        c.execute("SELECT user_id FROM usuarios WHERE user_id = %s", (int(limpio),))
    else:
        c.execute("SELECT user_id FROM usuarios WHERE LOWER(username) = %s", (limpio,))
    fila = c.fetchone()
    c.close()
    conn.close()
    if fila:
        return fila[0]
    return int(limpio) if limpio.isdigit() else None

def contar_stock(producto):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stock WHERE producto = %s AND vendido = 0", (producto,))
    cantidad = c.fetchone()[0]
    c.close()
    conn.close()
    return cantidad

def buscar_producto_nombre(texto_busqueda):
    texto_limpio = texto_busqueda.strip().lower()
    for prod in obtener_catalogo().keys():
        if prod.lower() == texto_limpio or texto_limpio in prod.lower():
            return prod
    return None

def limpiar_estados_usuario(user_id):
    compras_pendientes.pop(user_id, None)
    estado_carga_admin.pop(user_id, None)
    estado_precio_admin.pop(user_id, None)
    estado_mod_nombre.pop(user_id, None)
    estado_mod_desc.pop(user_id, None)
    estado_agregar_plat.pop(user_id, None)
    esperando_ticket_soporte.discard(user_id)
    estado_notificacion_admin.pop(user_id, None)
    esperando_noti_global.discard(user_id)

def boton_volver_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏠 Menú Principal", callback_data="inicio"))
    return markup

def enviar_archivo_txt(chat_id, contenido_texto, nombre_archivo, caption=""):
    archivo_memoria = io.BytesIO(contenido_texto.encode("utf-8"))
    archivo_memoria.name = nombre_archivo
    bot.send_document(chat_id, archivo_memoria, caption=caption, parse_mode="Markdown", reply_markup=boton_volver_menu())

def verificar_pago_binance(order_id_cliente, monto_esperado):
    url = "url = "https://bpay.binanceapi.com/binancepay/openapi/v2/order/query"
    timestamp = int(time.time() * 1000)
    query_string = urlencode({"timestamp": timestamp, "limit": 50})
    
    signature = hmac.new(
        BINANCE_SECRET_KEY.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    full_url = f"{url}?{query_string}&signature={signature}"
    
    try:
        resp = requests.get(full_url, headers=headers, timeout=10).json()
        if not resp.get("success"):
            return False, "Error conectando con la API de Binance."
        
        for tx in resp.get("data", []):
            tx_order_id = str(tx.get("orderId", ""))
            tx_prepay_id = str(tx.get("prepayId", ""))
            monto_tx = float(tx.get("amount", 0))
            moneda = tx.get("currency", "")
            
            id_limpio = str(order_id_cliente).strip()
            if (id_limpio == tx_order_id or id_limpio == tx_prepay_id):
                if moneda != "USDT":
                    return False, f"La moneda es {moneda}. Solo se acepta USDT."
                if abs(monto_tx - monto_esperado) > 0.05:
                    return False, f"Monto incorrecto. Pagaste {monto_tx} USDT y se requerían {monto_esperado} USDT."
                return True, monto_tx
                
        return False, "No se encontró ese ID de orden en Binance Pay."
    except Exception as e:
        return False, f"Error de red: {e}"

# ================= VISTAS DE MENÚ =================
def vista_menu_principal(user):
    registrar_o_actualizar_usuario(user)
    uid, uname, nombre, _ = obtener_datos_usuario(user.id)
    rango = "👑 ADMINISTRADOR" if uid == ADMIN_ID else "👤 Cliente"
    texto = (
        f"⚡ *SA SHOP — TIENDA AUTOMÁTICA 24/7* ⚡\n\n"
        f"┏ 👤 *Usuario:* {nombre} (`{uname}`)\n"
        f"┣ 🎖️ *Rol:* {rango}\n"
        f"┗ 🆔 *ID:* `{uid}`\n\n"
        f"👇 Selecciona una opción en los botones:"
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🛒 Ver Catálogo y Comprar", callback_data="catalogo"),
        InlineKeyboardButton("👤 Mi Perfil e Historial", callback_data="perfil"),
        InlineKeyboardButton("🛠️ Soporte y Ayuda", callback_data="soporte")
    )
    if uid == ADMIN_ID:
        markup.add(InlineKeyboardButton("👑 Panel de Administración (/cmds)", callback_data="panel_admin"))
    return texto, markup

def vista_catalogo(user_id):
    catalogo = obtener_catalogo()
    markup = InlineKeyboardMarkup(row_width=1)
    for prod, info in catalogo.items():
        precio = info["precio"]
        desc = info["desc"]
        es_correo = "correo" in desc.lower() or "activación" in desc.lower()
        
        if es_correo:
            texto_boton = f"🟢 {prod} — {precio:.2f} USDT | ✉️ {desc}"
        else:
            disp = contar_stock(prod)
            if disp > 0:
                texto_boton = f"🟢 {prod} — {precio:.2f} USDT ({disp} disp.)"
            else:
                texto_boton = f"🔴 {prod} — {precio:.2f} USDT (Agotado)"
        markup.add(InlineKeyboardButton(texto_boton, callback_data=f"sel_{prod}"))
    markup.add(InlineKeyboardButton("🏠 Menú Principal", callback_data="inicio"))
    
    texto = (
        f"🛒 *CATÁLOGO DE PRODUCTOS DISPONIBLES*\n\n"
        f"🟢 Disponible | 🔴 Agotado\n"
        f"👇 Elige el producto que deseas adquirir:"
    )
    return texto, markup

@bot.message_handler(commands=["start", "menu", "menú", "inicio"])
def cmd_start(message):
    limpiar_estados_usuario(message.from_user.id)
    texto, markup = vista_menu_principal(message.from_user)
    bot.send_message(message.chat.id, texto, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=["buy", "catalogo", "catálogo"])
def cmd_buy_directo(message):
    registrar_o_actualizar_usuario(message.from_user)
    limpiar_estados_usuario(message.from_user.id)
    texto, markup = vista_catalogo(message.from_user.id)
    bot.send_message(message.chat.id, texto, reply_markup=markup, parse_mode="Markdown")

# ================= COMANDOS DE ADMIN =================
TEXTO_CMDS_ADMIN = (
    "╔════════════════════════════════╗\n"
    "║     👑 **PANEL DE CONTROL ADMIN**     ║\n"
    "╚════════════════════════════════╝\n\n"
    "📦 **GESTIÓN DE CATÁLOGO Y STOCK**\n"
    "  • `/agregar_plataforma` ➔ Crear nuevo producto\n"
    "  • `/quitar_plataforma` ➔ Eliminar producto\n"
    "  • `/modificar_nombre` ➔ Cambiar nombre de plataforma\n"
    "  • `/modificar_precio` ➔ Cambiar precio de producto\n"
    "  • `/modificar_descripcion` ➔ Cambiar descripción/modalidad\n"
    "  • `/cargar` ➔ Subir cuentas por lotes\n"
    "  • `/stock` ➔ Ver reporte y descargar TXT general\n"
    "  • `/borrar [ID]` ➔ Eliminar cuenta específica\n"
    "  • `/vaciar [nombre]` ➔ Limpiar stock no vendido\n\n"
    "📢 **COMUNICACIÓN Y DIFUSIÓN**\n"
    "  • `/noti` ➔ Anuncio global (foto o texto)\n"
    "  • `/enviar [ID/@user]` ➔ Mensaje privado a cliente\n\n"
    "👥 **CLIENTES Y ESTADÍSTICAS**\n"
    "  • `/historial [ID/@user]` ➔ Ver compras del cliente\n"
    "  • `/stats` ➔ Métricas y finanzas de la tienda\n"
    "  • `/usuarios` ➔ Base de datos completa en TXT"
)

@bot.message_handler(commands=["cmds", "admin", "ayuda"])
def cmd_cmds_admin(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, TEXTO_CMDS_ADMIN, reply_markup=boton_volver_menu(), parse_mode="Markdown")

@bot.message_handler(commands=["agregar_plataforma"])
def cmd_agregar_plataforma(message):
    if message.from_user.id != ADMIN_ID:
        return
    limpiar_estados_usuario(ADMIN_ID)
    estado_agregar_plat[ADMIN_ID] = {"paso": "nombre"}
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="inicio"))
    bot.reply_to(
        message,
        "➕ **CREAR NUEVA PLATAFORMA**\n\nPaso 1/3: Envía el **nombre** de la nueva plataforma (Ejemplo: `Paramount+`):",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["quitar_plataforma"])
def cmd_quitar_plataforma(message):
    if message.from_user.id != ADMIN_ID:
        return
    limpiar_estados_usuario(ADMIN_ID)
    catalogo = obtener_catalogo()
    
    markup = InlineKeyboardMarkup(row_width=1)
    for prod in catalogo.keys():
        markup.add(InlineKeyboardButton(f"🗑️ Eliminar: {prod}", callback_data=f"delplat_{prod}"))
    markup.add(InlineKeyboardButton("🏠 Menú Principal", callback_data="inicio"))

    bot.reply_to(
        message,
        "🗑️ **ELIMINAR PLATAFORMA DEL CATÁLOGO**\n\nSelecciona el producto que deseas retirar permanentemente:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["modificar_nombre"])
def cmd_modificar_nombre(message):
    if message.from_user.id != ADMIN_ID:
        return
    limpiar_estados_usuario(ADMIN_ID)
    catalogo = obtener_catalogo()
    
    markup = InlineKeyboardMarkup(row_width=1)
    for prod in catalogo.keys():
        markup.add(InlineKeyboardButton(f"✏️ Renombrar: {prod}", callback_data=f"modnom_{prod}"))
    markup.add(InlineKeyboardButton("🏠 Menú Principal", callback_data="inicio"))

    bot.reply_to(
        message,
        "✏️ **MODIFICAR NOMBRE DE PLATAFORMA**\n\nSelecciona el producto al que deseas cambiarle el nombre:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["modificar_precio"])
def cmd_modificar_precio(message):
    if message.from_user.id != ADMIN_ID:
        return
    limpiar_estados_usuario(ADMIN_ID)
    catalogo = obtener_catalogo()
    
    markup = InlineKeyboardMarkup(row_width=1)
    for prod, info in catalogo.items():
        markup.add(InlineKeyboardButton(f"💵 {prod} (Actual: {info['precio']:.2f} USDT)", callback_data=f"prec_{prod}"))
    markup.add(InlineKeyboardButton("🏠 Menú Principal", callback_data="inicio"))

    bot.reply_to(
        message,
        "💵 **MODIFICAR PRECIOS DE PRODUCTOS**\n\nSelecciona el producto al que deseas cambiarle el precio:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["modificar_descripcion"])
def cmd_modificar_descripcion(message):
    if message.from_user.id != ADMIN_ID:
        return
    limpiar_estados_usuario(ADMIN_ID)
    catalogo = obtener_catalogo()
    
    markup = InlineKeyboardMarkup(row_width=1)
    for prod, info in catalogo.items():
        markup.add(InlineKeyboardButton(f"📌 {prod} (Actual: {info['desc']})", callback_data=f"moddesc_{prod}"))
    markup.add(InlineKeyboardButton("🏠 Menú Principal", callback_data="inicio"))

    bot.reply_to(
        message,
        "📌 **MODIFICAR DESCRIPCIÓN O MODALIDAD**\n\nSelecciona el producto al que deseas cambiarle la descripción:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["stock"])
def cmd_consultar_stock(message):
    registrar_o_actualizar_usuario(message.from_user)
    partes = message.text.split(maxsplit=1)
    es_admin = (message.from_user.id == ADMIN_ID)
    catalogo = obtener_catalogo()
    
    if len(partes) == 1:
        lineas = ["📊 **ESTADO GENERAL DEL INVENTARIO Y CATÁLOGO**\n"]
        for prod, info in catalogo.items():
            precio = info["precio"]
            desc = info["desc"]
            es_correo = "correo" in desc.lower() or "activación" in desc.lower()
            
            if es_correo:
                lineas.append(f"🟢 **{prod}** ➔ `{precio:.2f} USDT` | ✉️ {desc}")
            else:
                cant = contar_stock(prod)
                color = "🟢" if cant > 0 else "🔴"
                lineas.append(f"{color} **{prod}** ➔ `{cant}` disp. (`{precio:.2f} USDT`) | 📌 {desc}")
        
        bot.reply_to(message, "\n".join(lineas), reply_markup=boton_volver_menu(), parse_mode="Markdown")

        if es_admin:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id, producto, credenciales FROM stock WHERE vendido = 0 ORDER BY producto, id")
            filas = c.fetchall()
            c.close()
            conn.close()

            if filas:
                txt_lines = ["=== REPORTE GENERAL DE STOCK DISPONIBLE ===", ""]
                prod_actual = ""
                for sid, prod, cred in filas:
                    if prod != prod_actual:
                        prod_actual = prod
                        txt_lines.append(f"\n--- [{prod.upper()}] ---")
                    txt_lines.append(f"ID: {sid} | {cred}")
                enviar_archivo_txt(message.chat.id, "\n".join(txt_lines), "stock_general.txt", "🔐 **Archivo TXT con cuentas en inventario:**")
        return

    busqueda = partes[1]
    producto_encontrado = buscar_producto_nombre(busqueda)
    
    if not producto_encontrado:
        bot.reply_to(message, f"❌ No se encontró `{busqueda}` en el catálogo.", reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return

    info_prod = catalogo[producto_encontrado]
    precio_actual = info_prod["precio"]
    desc_prod = info_prod["desc"]
    es_correo = "correo" in desc_prod.lower() or "activación" in desc_prod.lower()

    if es_correo:
        bot.reply_to(message, f"📦 **{producto_encontrado}**\n💵 Precio: `{precio_actual:.2f} USDT`\n📌 Descripción: {desc_prod}", reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return

    cant = contar_stock(producto_encontrado)
    color = "🟢" if cant > 0 else "🔴"
    respuesta = f"📦 **Inventario:** {producto_encontrado}\n💵 **Precio:** `{precio_actual:.2f} USDT`\n📌 **Tipo:** {desc_prod}\n{color} **Disponibles:** `{cant}` unidades"
    bot.reply_to(message, respuesta, reply_markup=boton_volver_menu(), parse_mode="Markdown")
    
    if es_admin and cant > 0:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, credenciales FROM stock WHERE producto = %s AND vendido = 0", (producto_encontrado,))
        filas = c.fetchall()
        c.close()
        conn.close()
        
        contenido = f"=== STOCK DE {producto_encontrado.upper()} ({cant}) ===\n\n"
        contenido += "\n".join([f"ID: {f[0]} | {f[1]}" for f in filas])
        enviar_archivo_txt(message.chat.id, contenido, f"stock_{producto_encontrado.lower().replace(' ', '_')}.txt", f"🔐 **Credenciales de {producto_encontrado}:**")

@bot.message_handler(commands=["cargar"])
def cmd_cargar_menu(message):
    if message.from_user.id != ADMIN_ID:
        return
    limpiar_estados_usuario(ADMIN_ID)

    catalogo = obtener_catalogo()
    markup = InlineKeyboardMarkup(row_width=2)
    botones = []
    for prod, info in catalogo.items():
        if "correo" in info["desc"].lower() or "activación" in info["desc"].lower():
            continue
        cant = contar_stock(prod)
        color = "🟢" if cant > 0 else "🔴"
        botones.append(InlineKeyboardButton(f"{color} {prod} ({cant})", callback_data=f"cargar_{prod}"))
    markup.add(*botones)
    markup.add(InlineKeyboardButton("🏠 Menú Principal", callback_data="inicio"))

    bot.reply_to(
        message,
        "📥 **PANEL DE CARGA DE INVENTARIO**\n\nSelecciona el producto al que deseas subir cuentas:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["historial"])
def cmd_historial_admin(message):
    if message.from_user.id != ADMIN_ID:
        return
    partes = message.text.split(maxsplit=1)
    if len(partes) < 2:
        bot.reply_to(message, "⚠️ **Uso correcto:**\n`/historial [ID o @username]`", reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return

    target_id = buscar_id_por_id_o_username(partes[1])
    if not target_id:
        bot.reply_to(message, "❌ Cliente no encontrado en la base de datos.", reply_markup=boton_volver_menu())
        return

    uid, uname, nombre, total_compras = obtener_datos_usuario(target_id)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, producto, credenciales, precio, fecha FROM historial_compras WHERE user_id = %s ORDER BY id DESC", (uid,))
    compras_lista = c.fetchall()
    c.close()
    conn.close()

    resumen = (
        f"📋 **EXPEDIENTE DEL CLIENTE**\n\n"
        f"👤 **Nombre:** {nombre} (`{uname}`)\n"
        f"🆔 **ID:** `{uid}`\n"
        f"🛍️ **Compras exitosas:** `{len(compras_lista)}`"
    )
    bot.reply_to(message, resumen, reply_markup=boton_volver_menu(), parse_mode="Markdown")

    if compras_lista:
        lineas_txt = [f"=== HISTORIAL DE COMPRAS: {uid} ({uname}) ===", f"Cliente: {nombre} | Total compras: {len(compras_lista)}", "="*60 + "\n"]
        for cid, prod, cred, prec, fec in compras_lista:
            lineas_txt.append(f"[Compra #{cid}] Fecha: {fec} | {prod} | Pagado: {prec:.2f} USDT")
            lineas_txt.append(f"Datos: {cred}")
            lineas_txt.append("-" * 50)
        enviar_archivo_txt(message.chat.id, "\n".join(lineas_txt), f"historial_{uid}.txt", f"📂 **Archivo TXT de compras del usuario `{uid}`:**")

@bot.message_handler(commands=["noti"])
def cmd_noti_global(message):
    if message.from_user.id != ADMIN_ID:
        return
    limpiar_estados_usuario(ADMIN_ID)
    esperando_noti_global.add(ADMIN_ID)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="inicio"))
    bot.reply_to(message, "📢 **MODO ANUNCIO GLOBAL**\n\nEnvía la **imagen con texto** o el **mensaje** que deseas difundir a todos:", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=["enviar"])
def cmd_notificar_individual(message):
    if message.from_user.id != ADMIN_ID:
        return
    partes = message.text.split(maxsplit=1)
    if len(partes) < 2:
        bot.reply_to(message, "⚠️ Uso: `/enviar [ID o @username]`", reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return
    target_id = buscar_id_por_id_o_username(partes[1].strip())
    if not target_id:
        bot.reply_to(message, "❌ Usuario no encontrado.", reply_markup=boton_volver_menu())
        return
    estado_notificacion_admin[ADMIN_ID] = target_id
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="inicio"))
    bot.reply_to(message, f"📨 Escribe el mensaje o imagen para el usuario `{target_id}`:", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=["borrar"])
def cmd_borrar_cuenta(message):
    if message.from_user.id != ADMIN_ID:
        return
    partes = message.text.split()
    if len(partes) != 2 or not partes[1].isdigit():
        bot.reply_to(message, "⚠️ Uso: `/borrar [ID_DE_CUENTA]`", parse_mode="Markdown")
        return
    sid = int(partes[1])
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM stock WHERE id = %s AND vendido = 0", (sid,))
    borrado = c.rowcount
    conn.commit()
    c.close()
    conn.close()
    if borrado:
        bot.reply_to(message, f"🗑️ Cuenta ID `{sid}` eliminada del inventario.", reply_markup=boton_volver_menu(), parse_mode="Markdown")
    else:
        bot.reply_to(message, f"❌ No se encontró cuenta disponible con ID `{sid}`.", reply_markup=boton_volver_menu(), parse_mode="Markdown")

@bot.message_handler(commands=["vaciar"])
def cmd_vaciar_producto(message):
    if message.from_user.id != ADMIN_ID:
        return
    partes = message.text.split(maxsplit=1)
    if len(partes) < 2:
        bot.reply_to(message, "⚠️ Uso: `/vaciar [nombre_plataforma]`", parse_mode="Markdown")
        return
    prod = buscar_producto_nombre(partes[1])
    if not prod:
        bot.reply_to(message, "❌ Producto no encontrado.")
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM stock WHERE producto = %s AND vendido = 0", (prod,))
    cant = c.rowcount
    conn.commit()
    c.close()
    conn.close()
    bot.reply_to(message, f"🗑️ Se eliminaron `{cant}` cuentas no vendidas de *{prod}*.", reply_markup=boton_volver_menu(), parse_mode="Markdown")

@bot.message_handler(commands=["stats"])
def cmd_stats_admin(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM usuarios")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*), COALESCE(SUM(precio), 0) FROM historial_compras")
    ventas_totales, ingresos = c.fetchone()
    c.execute("SELECT COUNT(*), COALESCE(SUM(monto), 0) FROM pagos_usados")
    pagos_count, total_pagado = c.fetchone()
    c.execute("SELECT COUNT(*) FROM stock WHERE vendido = 0")
    stock_disp = c.fetchone()[0]
    c.close()
    conn.close()

    texto = (
        f"📈 **ESTADÍSTICAS GENERALES DE LA TIENDA**\n\n"
        f"👥 Clientes registrados: `{total_users}`\n"
        f"🛍️ Productos vendidos: `{ventas_totales}`\n"
        f"💵 Ingresos totales: `{ingresos:.2f} USDT`\n"
        f"💎 Transacciones Binance Pay: `{pagos_count}` (`{total_pagado:.2f} USDT`)\n"
        f"📦 Cuentas listas en stock: `{stock_disp}`"
    )
    bot.reply_to(message, texto, reply_markup=boton_volver_menu(), parse_mode="Markdown")

@bot.message_handler(commands=["usuarios"])
def cmd_usuarios_txt(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, nombre, compras, fecha_registro FROM usuarios ORDER BY fecha_registro DESC")
    filas = c.fetchall()
    c.close()
    conn.close()

    lineas = ["=== BASE DE DATOS DE CLIENTES ===\n"]
    for uid, uname, nom, comp, fec in filas:
        lineas.append(f"ID: {uid} | @{uname or 'Sin_user'} | {nom} | Compras: {comp} | Registro: {fec}")
    enviar_archivo_txt(message.chat.id, "\n".join(lineas), "clientes_tienda.txt", f"👥 **Listado de `{len(filas)}` clientes registrados:**")

# ================= CALLBACKS Y FLUJO DE COMPRA / ADMIN =================
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    user = call.from_user
    user_id = user.id
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    registrar_o_actualizar_usuario(user)

    if call.data == "inicio":
        limpiar_estados_usuario(user_id)
        texto, markup = vista_menu_principal(user)
        try:
            bot.edit_message_text(texto, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "panel_admin":
        if user_id != ADMIN_ID:
            return
        bot.edit_message_text(TEXTO_CMDS_ADMIN, chat_id, msg_id, reply_markup=boton_volver_menu(), parse_mode="Markdown")

    elif call.data == "catalogo":
        limpiar_estados_usuario(user_id)
        texto, markup = vista_catalogo(user_id)
        bot.edit_message_text(texto, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("delplat_"):
        if user_id != ADMIN_ID:
            return
        producto = call.data.split("_", 1)[1]
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM catalogo_db WHERE producto = %s", (producto,))
        conn.commit()
        c.close()
        conn.close()
        
        bot.answer_callback_query(call.id, f"✅ {producto} eliminado.", show_alert=True)
        texto, markup = vista_catalogo(user_id)
        bot.edit_message_text(f"🗑️ Plataforma `{producto}` eliminada con éxito.\n\n" + texto, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("modnom_"):
        if user_id != ADMIN_ID:
            return
        producto = call.data.split("_", 1)[1]
        estado_mod_nombre[user_id] = producto
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="inicio"))
        bot.edit_message_text(
            f"✏️ **CAMBIAR NOMBRE A:** `{producto}`\n\n👉 **Escribe el nuevo nombre** para esta plataforma en el chat:",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown"
        )

    elif call.data.startswith("moddesc_"):
        if user_id != ADMIN_ID:
            return
        producto = call.data.split("_", 1)[1]
        estado_mod_desc[user_id] = producto
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="inicio"))
        bot.edit_message_text(
            f"📌 **CAMBIAR DESCRIPCIÓN A:** `{producto}`\n\n👉 **Escribe la nueva descripción/modalidad** (Ej: `email:pass`, `link`, etc.):",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown"
        )

    elif call.data.startswith("prec_"):
        if user_id != ADMIN_ID:
            return
        producto = call.data.split("_", 1)[1]
        estado_precio_admin[user_id] = producto
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="inicio"))
        bot.edit_message_text(
            f"💵 **CAMBIAR PRECIO A:** `{producto}`\n\nPrecio actual: `{obtener_precio(producto):.2f} USDT`\n\n👉 **Escribe el nuevo precio en el chat** (Ejemplo: `3.50`):",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown"
        )

    elif call.data.startswith("sel_"):
        producto = call.data.split("_", 1)[1]
        precio = obtener_precio(producto)
        es_correo = es_producto_a_correo(producto)

        if es_correo:
            compras_pendientes[user_id] = {"producto": producto, "tipo": "correo"}
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="catalogo"))
            bot.edit_message_text(
                f"📧 **{producto.upper()} (Activación a correo)**\n\n"
                f"💵 Precio: `{precio:.2f} USDT`\n\n"
                f"👉 **Envía ahora en el chat tu correo electrónico** para continuar:",
                chat_id, msg_id, reply_markup=markup, parse_mode="Markdown"
            )
            return

        stock_disp = contar_stock(producto)
        if stock_disp <= 0:
            bot.answer_callback_query(call.id, f"🔴 {producto} está agotado.", show_alert=True)
            return

        compras_pendientes[user_id] = {"producto": producto, "cantidad": 1, "precio_unit": precio, "tipo": "stock"}
        texto, markup = menu_cantidad(producto, 1, precio, stock_disp)
        bot.edit_message_text(texto, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("cant_"):
        partes = call.data.split("_")
        accion = partes[1]
        producto = partes[2]
        
        if user_id not in compras_pendientes:
            bot.answer_callback_query(call.id, "La sesión expiró. Vuelve al catálogo.", show_alert=True)
            return

        stock_disp = contar_stock(producto)
        cant_actual = compras_pendientes[user_id]["cantidad"]
        precio_unit = obtener_precio(producto)
        compras_pendientes[user_id]["precio_unit"] = precio_unit

        if accion == "mas":
            if cant_actual < stock_disp:
                cant_actual += 1
        elif accion == "menos":
            if cant_actual > 1:
                cant_actual -= 1
        elif accion == "ok":
            compras_pendientes[user_id]["cantidad"] = cant_actual
            total_pagar = cant_actual * precio_unit
            
            texto_pago = (
                f"💎 **PAGO DIRECTO CON BINANCE PAY** 💎\n\n"
                f"📦 **Producto:** {producto} (x{cant_actual})\n"
                f"💵 **Total a depositar:** `{total_pagar:.2f} USDT`\n\n"
                f"1️⃣ Abre Binance y ve a **Pay ➔ Enviar**.\n"
                f"2️⃣ Envía exactos **{total_pagar:.2f} USDT** al ID:\n"
                f"👉 `{BINANCE_PAY_ID}`\n\n"
                f"3️⃣ **Pega aquí abajo en el chat el Order ID** de tu transacción para recibir tu entrega inmediata:"
            )
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="catalogo"))
            bot.edit_message_text(texto_pago, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
            return

        compras_pendientes[user_id]["cantidad"] = cant_actual
        texto, markup = menu_cantidad(producto, cant_actual, precio_unit, stock_disp)
        bot.edit_message_text(texto, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif call.data.startswith("cargar_"):
        if user_id != ADMIN_ID:
            return
        producto = call.data.split("_", 1)[1]
        estado_carga_admin[user_id] = producto
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="inicio"))
        bot.edit_message_text(
            f"📥 **Cargando stock para:** `{producto}`\n\nEnvía las cuentas en formato `correo:contraseña` (varias líneas permitidas):",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown"
        )

    elif call.data == "perfil":
        uid, uname, nombre, compras = obtener_datos_usuario(user_id)
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT producto, credenciales, fecha FROM historial_compras WHERE user_id = %s ORDER BY id DESC LIMIT 5", (user_id,))
        ultimas = c.fetchall()
        c.close()
        conn.close()

        historial_txt = ""
        if ultimas:
            historial_txt = "\n\n📋 **Tus últimas compras:**\n" + "\n".join([f"• *{p}*: `{cr}`" for p, cr, _ in ultimas])

        texto = (
            f"👤 **INFORMACIÓN DE TU CUENTA**\n\n"
            f"🏷️ Nombre: {nombre}\n"
            f"🔗 Username: `{uname}`\n"
            f"🆔 ID: `{uid}`\n"
            f"🛍️ Compras totales: `{compras}`"
            f"{historial_txt}"
        )
        bot.edit_message_text(texto, chat_id, msg_id, reply_markup=boton_volver_menu(), parse_mode="Markdown")

    elif call.data == "soporte":
        limpiar_estados_usuario(user_id)
        esperando_ticket_soporte.add(user_id)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💬 Ir a Soporte Directo", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"),
                   InlineKeyboardButton("🏠 Menú Principal", callback_data="inicio"))
        bot.edit_message_text(
            "🛠️ **CENTRO DE SOPORTE**\n\nEscribe directamente tu consulta o reporte en el chat y el administrador te atenderá:",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown"
        )

def menu_cantidad(producto, cantidad, precio_unit, stock_disp):
    total = cantidad * precio_unit
    texto = (
        f"📦 **SELECCIONA LA CANTIDAD**\n\n"
        f"• Producto: `{producto}`\n"
        f"• Stock disponible: `{stock_disp}` unidades\n"
        f"• Precio unitario: `{precio_unit:.2f} USDT`\n\n"
        f"🔢 Cantidad seleccionada: **{cantidad}**\n"
        f"💵 **Total a pagar:** `{total:.2f} USDT`"
    )
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("➖ Quitar", callback_data=f"cant_menos_{producto}"),
        InlineKeyboardButton(f"🔢 {cantidad}", callback_data="nada"),
        InlineKeyboardButton("➕ Agregar", callback_data=f"cant_mas_{producto}")
    )
    markup.add(InlineKeyboardButton(f"💳 Pagar {total:.2f} USDT con Binance Pay", callback_data=f"cant_ok_{producto}"))
    markup.add(InlineKeyboardButton("⬅️ Volver al Catálogo", callback_data="catalogo"))
    return texto, markup

# ================= MANEJO DE ENTRADAS (TEXTO / FOTO) =================
@bot.message_handler(content_types=["text", "photo"])
def manejar_entradas(message):
    user = message.from_user
    user_id = user.id
    registrar_o_actualizar_usuario(user)

    # 1. MODIFICAR NOMBRE DE PLATAFORMA
    if user_id == ADMIN_ID and user_id in estado_mod_nombre:
        prod_antiguo = estado_mod_nombre.pop(user_id)
        nuevo_nombre = message.text.strip()
        
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE catalogo_db SET producto = %s WHERE producto = %s", (nuevo_nombre, prod_antiguo))
        c.execute("UPDATE stock SET producto = %s WHERE producto = %s", (nuevo_nombre, prod_antiguo))
        conn.commit()
        c.close()
        conn.close()

        bot.reply_to(message, f"✅ **¡Nombre actualizado con éxito!**\n\nDe: `{prod_antiguo}` ➔ A: `{nuevo_nombre}`", reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return

    # 2. MODIFICAR DESCRIPCIÓN DE PLATAFORMA
    if user_id == ADMIN_ID and user_id in estado_mod_desc:
        producto = estado_mod_desc.pop(user_id)
        nueva_desc = message.text.strip()
        
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE catalogo_db SET descripcion = %s WHERE producto = %s", (nueva_desc, producto))
        conn.commit()
        c.close()
        conn.close()

        bot.reply_to(message, f"✅ **¡Descripción actualizada!**\n\n📦 Producto: `{producto}`\n📌 Nueva descripción: `{nueva_desc}`", reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return

    # 3. AGREGAR NUEVA PLATAFORMA PASO A PASO
    if user_id == ADMIN_ID and user_id in estado_agregar_plat:
        estado = estado_agregar_plat[user_id]
        paso = estado["paso"]

        if paso == "nombre":
            nombre_prod = message.text.strip()
            estado["nombre"] = nombre_prod
            estado["paso"] = "precio"
            bot.reply_to(message, f"➕ Producto: `{nombre_prod}`\n\nPaso 2/3: Envía el **precio unitario** en USDT (Ejemplo: `3.50`):", reply_markup=boton_volver_menu(), parse_mode="Markdown")
            return
        elif paso == "precio":
            try:
                precio_prod = float(message.text.strip().replace(",", "."))
                if precio_prod < 0: raise ValueError()
                estado["precio"] = precio_prod
                estado["paso"] = "desc"
                bot.reply_to(message, "Paso 3/3: Envía la **descripción o modalidad** (Ejemplo: `email:pass`, `link de invitación` o `activación a correo`):", reply_markup=boton_volver_menu(), parse_mode="Markdown")
            except ValueError:
                bot.reply_to(message, "❌ Precio inválido. Envía un número (Ejemplo: `4.00`):", reply_markup=boton_volver_menu())
            return
        elif paso == "desc":
            desc_prod = message.text.strip()
            nombre_prod = estado["nombre"]
            precio_prod = estado["precio"]
            
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT INTO catalogo_db (producto, precio, descripcion) VALUES (%s, %s, %s) ON CONFLICT (producto) DO UPDATE SET precio = EXCLUDED.precio, descripcion = EXCLUDED.descripcion", (nombre_prod, precio_prod, desc_prod))
            conn.commit()
            c.close()
            conn.close()

            estado_agregar_plat.pop(user_id, None)
            bot.reply_to(
                message,
                f"✅ **¡Plataforma agregada con éxito!**\n\n📦 Nombre: `{nombre_prod}`\n💵 Precio: `{precio_prod:.2f} USDT`\n📌 Modalidad: `{desc_prod}`",
                reply_markup=boton_volver_menu(),
                parse_mode="Markdown"
            )
            return

    # 4. MODIFICAR PRECIO ADMIN
    if user_id == ADMIN_ID and user_id in estado_precio_admin:
        producto = estado_precio_admin.pop(user_id)
        texto_limpio = message.text.strip().replace(",", ".")
        try:
            nuevo_precio = float(texto_limpio)
            if nuevo_precio < 0: raise ValueError()
            
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE catalogo_db SET precio = %s WHERE producto = %s", (nuevo_precio, producto))
            conn.commit()
            c.close()
            conn.close()

            bot.reply_to(message, f"✅ **¡Precio actualizado!**\n\n📦 Producto: `{producto}`\n💵 Nuevo precio: `{nuevo_precio:.2f} USDT`", reply_markup=boton_volver_menu(), parse_mode="Markdown")
        except ValueError:
            bot.reply_to(message, "❌ Precio inválido. Envía un número (Ejemplo: `3.50`):", reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return

    # 5. NOTIFICACIÓN GLOBAL
    if user_id == ADMIN_ID and ADMIN_ID in esperando_noti_global:
        esperando_noti_global.discard(ADMIN_ID)
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id FROM usuarios")
        todos = [r[0] for r in c.fetchall()]
        c.close()
        conn.close()

        enviados = 0
        msg_estado = bot.reply_to(message, f"📢 Enviando difusión a `{len(todos)}` usuarios...", parse_mode="Markdown")
        for uid_destino in todos:
            try:
                if message.content_type == "photo":
                    bot.send_photo(uid_destino, message.photo[-1].file_id, caption=f"📢 **AVISO OFICIAL**\n\n{message.caption or ''}", reply_markup=boton_volver_menu(), parse_mode="Markdown")
                else:
                    bot.send_message(uid_destino, f"📢 **AVISO OFICIAL**\n\n{message.text}", reply_markup=boton_volver_menu(), parse_mode="Markdown")
                enviados += 1
                time.sleep(0.03)
            except Exception:
                pass
        bot.edit_message_text(f"✅ Difusión completada (`{enviados}/{len(todos)}`).", message.chat.id, msg_estado.message_id, reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return

    # 6. NOTIFICACIÓN INDIVIDUAL
    if user_id == ADMIN_ID and ADMIN_ID in estado_notificacion_admin:
        target_id = estado_notificacion_admin.pop(ADMIN_ID)
        try:
            if message.content_type == "photo":
                bot.send_photo(target_id, message.photo[-1].file_id, caption=f"🔔 **MENSAJE DEL ADMIN:**\n\n{message.caption or ''}", reply_markup=boton_volver_menu(), parse_mode="Markdown")
            else:
                bot.send_message(target_id, f"🔔 **MENSAJE DEL ADMIN:**\n\n{message.text}", reply_markup=boton_volver_menu(), parse_mode="Markdown")
            bot.reply_to(message, f"✅ Mensaje enviado al cliente `{target_id}`.", reply_markup=boton_volver_menu())
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {e}", reply_markup=boton_volver_menu())
        return

    # 7. SOPORTE CLIENTE
    if user_id in esperando_ticket_soporte:
        esperando_ticket_soporte.discard(user_id)
        uid, uname, nombre, _ = obtener_datos_usuario(user_id)
        header = f"🆘 **REPORTE DE SOPORTE**\n\n👤 {nombre} (`{uname}`)\n🆔 ID: `{uid}`"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📨 Responder", callback_data=f"noti_{uid}"))
        
        if message.content_type == "photo":
            bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"{header}\n\nMensaje: {message.caption or ''}", reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(ADMIN_ID, f"{header}\n\nMensaje:\n{message.text}", reply_markup=markup, parse_mode="Markdown")
        bot.reply_to(message, "✅ Mensaje enviado a soporte. Te responderemos pronto.", reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return

    if message.content_type != "text":
        return

    texto = message.text.strip()

    # 8. CARGA DE STOCK ADMIN
    if user_id == ADMIN_ID and user_id in estado_carga_admin:
        producto = estado_carga_admin.pop(user_id)
        lineas = [l.strip() for l in texto.split("\n") if l.strip()]
        conn = get_db()
        c = conn.cursor()
        for cred in lineas:
            c.execute("INSERT INTO stock (producto, credenciales) VALUES (%s, %s)", (producto, cred))
        conn.commit()
        c.close()
        conn.close()
        bot.reply_to(message, f"✅ Se agregaron `{len(lineas)}` cuentas a *{producto}*.", reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return

    # 9. CORREO PARA PRODUCTOS A CORREO
    if user_id in compras_pendientes and compras_pendientes[user_id].get("tipo") == "correo":
        if "@" not in texto or "." not in texto or " " in texto:
            bot.reply_to(message, "⚠️ Correo inválido. Escribe un correo correcto:", parse_mode="Markdown")
            return
        
        compra_info = compras_pendientes[user_id]
        producto = compra_info["producto"]
        precio = obtener_precio(producto)
        
        compras_pendientes[user_id] = {"producto": producto, "cantidad": 1, "precio_unit": precio, "correo": texto, "tipo": "pago_correo"}
        
        total_pagar = precio
        texto_pago = (
            f"💎 **PAGO DIRECTO CON BINANCE PAY**\n\n"
            f"📦 Producto: {producto} (Activación a correo)\n"
            f"📧 Correo: `{texto}`\n"
            f"💵 **Total a pagar:** `{total_pagar:.2f} USDT`\n\n"
            f"Envía exactos **{total_pagar:.2f} USDT** al Binance Pay ID:\n"
            f"👉 `{BINANCE_PAY_ID}`\n\n"
            f"Pega aquí tu **Order ID** de pago:"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="catalogo"))
        bot.reply_to(message, texto_pago, reply_markup=markup, parse_mode="Markdown")
        return

    # 10. VERIFICACIÓN DE ORDER ID DE BINANCE PAY Y ENTREGA INMEDIATA
    if user_id in compras_pendientes or (texto.isdigit() and len(texto) >= 15):
        if user_id not in compras_pendientes:
            bot.reply_to(message, "⚠️ No tienes ninguna compra en proceso. Selecciona un producto en el catálogo primero.", reply_markup=boton_volver_menu())
            return

        compra_info = compras_pendientes[user_id]
        producto = compra_info["producto"]
        cantidad = compra_info.get("cantidad", 1)
        precio_unit = obtener_precio(producto)
        total_esperado = cantidad * precio_unit
        tipo_compra = compra_info.get("tipo")
        correo_destino = compra_info.get("correo")

        order_id = texto
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT order_id FROM pagos_usados WHERE order_id = %s", (order_id,))
        if c.fetchone():
            c.close()
            conn.close()
            bot.reply_to(message, "❌ Este ID de transacción ya fue utilizado en otra compra.", reply_markup=boton_volver_menu())
            return

        msg_espera = bot.reply_to(message, "⏳ Verificando pago con Binance Pay...")
        exito, resultado = verificar_pago_binance(order_id, total_esperado)

        if not exito:
            c.close()
            conn.close()
            bot.edit_message_text(f"❌ **Error en la validación:**\n{resultado}", message.chat.id, msg_espera.message_id, reply_markup=boton_volver_menu(), parse_mode="Markdown")
            return

        c.execute("INSERT INTO pagos_usados (order_id, user_id, monto) VALUES (%s, %s, %s)", (order_id, user_id, total_esperado))

        # Caso A: Producto a Correo
        if tipo_compra == "pago_correo":
            c.execute("INSERT INTO historial_compras (user_id, producto, credenciales, precio) VALUES (%s, %s, %s, %s)",
                      (user_id, producto, f"Activación a correo: {correo_destino}", total_esperado))
            c.execute("UPDATE usuarios SET compras = compras + 1 WHERE user_id = %s", (user_id,))
            conn.commit()
            c.close()
            conn.close()
            compras_pendientes.pop(user_id, None)

            bot.edit_message_text(
                f"✅ **¡PAGO VERIFICADO Y PEDIDO REGISTRADO!**\n\n"
                f"📦 Producto: {producto}\n"
                f"📧 Correo: `{correo_destino}`\n"
                f"💵 Pagado: `{total_esperado:.2f} USDT`\n\n"
                f"⏳ En breve te enviaremos tu acceso.",
                message.chat.id, msg_espera.message_id, reply_markup=boton_volver_menu(), parse_mode="Markdown"
            )

            uid, uname, nombre, _ = obtener_datos_usuario(user_id)
            alerta_admin = (
                f"🔔 **NUEVA COMPRA A CORREO ({producto})**\n\n"
                f"👤 Cliente: {nombre} (`{uname}`)\n"
                f"🆔 ID: `{uid}`\n"
                f"📧 Correo: `{correo_destino}`\n"
                f"💵 Pagado: `{total_esperado:.2f} USDT`"
            )
            markup_admin = InlineKeyboardMarkup()
            markup_admin.add(InlineKeyboardButton("📸 Notificar Cliente", callback_data=f"noti_{uid}"))
            bot.send_message(ADMIN_ID, alerta_admin, reply_markup=markup_admin, parse_mode="Markdown")
            return

        # Caso B: Stock Inmediato
        c.execute("SELECT id, credenciales FROM stock WHERE producto = %s AND vendido = 0 LIMIT %s", (producto, cantidad))
        filas = c.fetchall()

        if len(filas) < cantidad:
            c.close()
            conn.close()
            bot.edit_message_text("❌ Lo sentimos, el stock se agotó justo al procesar el pago. Contacta a soporte para un reembolso inmediato.", message.chat.id, msg_espera.message_id, reply_markup=boton_volver_menu())
            return

        cuentas_entregadas = []
        for sid, cred in filas:
            c.execute("UPDATE stock SET vendido = 1 WHERE id = %s", (sid,))
            cuentas_entregadas.append(cred)

        c.execute("UPDATE usuarios SET compras = compras + 1 WHERE user_id = %s", (user_id,))
        c.execute("INSERT INTO historial_compras (user_id, producto, credenciales, precio) VALUES (%s, %s, %s, %s)",
                  (user_id, producto, " | ".join(cuentas_entregadas), total_esperado))
        conn.commit()
        c.close()
        conn.close()
        compras_pendientes.pop(user_id, None)

        bloque_cuentas = "\n".join([f"• `{c}`" for c in cuentas_entregadas])
        recibo = (
            f"🎉 **¡COMPRA EXITOSA Y ENTREGA INMEDIATA!** 🎉\n\n"
            f"📦 Producto: `{producto}` (x{cantidad})\n"
            f"💵 Pagado: `{total_esperado:.2f} USDT`\n\n"
            f"🔑 **Tus cuentas / accesos:**\n{bloque_cuentas}\n\n"
            f"¡Gracias por tu compra en SA SHOP!"
        )
        
        bot.edit_message_text(recibo, message.chat.id, msg_espera.message_id, reply_markup=boton_volver_menu(), parse_mode="Markdown")
        return

    bot.reply_to(message, "💡 Usa `/menu` para ir al inicio:", reply_markup=boton_volver_menu(), parse_mode="Markdown")

# ================= ARRANQUE =================
if __name__ == "__main__":
    keep_alive()
    print("🚀 Bot SA SHOP Pro 24/7 conectado a Supabase...")
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Error en polling: {e}")
            time.sleep(5)
