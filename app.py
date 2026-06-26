from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import sqlite3, os, uuid, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app, origins=["https://nucleocert.com", "http://nucleocert.com", "https://www.nucleocert.com"])

DB = "/root/cert/cert.db"
NKL_DB = "/root/nkl/nkl_pool.db"

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_VERIFY_SID = os.getenv("TWILIO_VERIFY_SID", "")
GMAIL_USER = "nucleonkl@gmail.com"
GMAIL_PASS = "ozdctslztmukedcw"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_nkl_db():
    conn = sqlite3.connect(NKL_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS paises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        bandera TEXT,
        estado TEXT DEFAULT 'en_preparacion',
        moneda TEXT,
        precio_certificado INTEGER DEFAULT 0,
        disclaimer_legal TEXT
    );
    CREATE TABLE IF NOT EXISTS tramites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_cert TEXT UNIQUE,
        pais_codigo TEXT DEFAULT 'AR',
        categoria TEXT,
        tipo_tramite TEXT,
        fecha_creacion TEXT,
        fecha_certificacion TEXT,
        hash_documento TEXT,
        estado TEXT DEFAULT 'borrador',
        modo TEXT DEFAULT 'presencial',
        estado_pago TEXT DEFAULT 'pendiente',
        mp_preference_id TEXT,
        mp_payment_id TEXT,
        monto_total INTEGER DEFAULT 0,
        solicitante_nombre TEXT,
        solicitante_doc TEXT,
        solicitante_tipo TEXT,
        solicitante_email TEXT,
        solicitante_telefono TEXT,
        licencia_nkl INTEGER DEFAULT 0,
        minero_username TEXT,
        emails_enviados INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS partes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tramite_id INTEGER,
        rol TEXT,
        nombre_completo TEXT,
        dni_numero TEXT,
        sms_verificado INTEGER DEFAULT 0,
        firma_timestamp TEXT,
        link_uuid TEXT UNIQUE,
        completado INTEGER DEFAULT 0,
        email TEXT,
        FOREIGN KEY (tramite_id) REFERENCES tramites(id)
    );
    INSERT OR IGNORE INTO paises (codigo, nombre, bandera, estado, moneda, precio_certificado, disclaimer_legal)
    VALUES (
        'AR', 'Argentina', '🇦🇷', 'activo', 'ARS', 10000,
        'Núcleo CERT es un servicio de certificación privada de fecha cierta e identidad de firmantes. No reemplaza la escritura pública en los actos que la ley argentina exige dicha forma (art. 1017 CCCN). Para consultas sobre validez legal consulte a un profesional habilitado.'
    );
    """)
    conn.commit()
    conn.close()

def enviar_email(destinatario, nombre, link, numero_cert, tipo_tramite, solicitante):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Núcleo CERT — Invitación a firmar: {tipo_tramite}"
        msg["From"] = f"Núcleo CERT <{GMAIL_USER}>"
        msg["To"] = destinatario

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f0f7f2;padding:32px">
          <div style="background:#fff;border-radius:12px;padding:32px;border:1px solid #e5e7eb">
            <div style="text-align:center;margin-bottom:24px">
              <h1 style="color:#2d9b5a;font-size:22px;margin:0">Núcleo CERT</h1>
              <p style="color:#5a6b57;font-size:13px;margin:4px 0">Certificación privada · Prueba permanente</p>
            </div>
            <p style="color:#111;font-size:16px">Hola <strong>{nombre}</strong>,</p>
            <p style="color:#374334;font-size:14px;line-height:1.7">
              <strong>{solicitante}</strong> te invitó a firmar el siguiente documento:
            </p>
            <div style="background:#f0f7f2;border-radius:8px;padding:16px;margin:20px 0;text-align:center">
              <p style="font-size:13px;color:#5a6b57;margin:0 0 4px">Trámite</p>
              <p style="font-size:16px;font-weight:700;color:#111;margin:0">{tipo_tramite}</p>
              <p style="font-size:12px;color:#9aab97;margin:8px 0 0">Certificado N° {numero_cert}</p>
            </div>
            <p style="color:#374334;font-size:14px;line-height:1.7">
              Para completar tu firma necesitás:
            </p>
            <ul style="color:#374334;font-size:13px;line-height:2">
              <li>DNI físico (frente y dorso)</li>
              <li>Tu celular con cámara</li>
              <li>Acceso a tu número de teléfono para verificación SMS</li>
            </ul>
            <div style="text-align:center;margin:32px 0">
              <a href="{link}" style="background:#2d9b5a;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-size:16px;font-weight:700;display:inline-block">
                Firmar ahora →
              </a>
            </div>
            <p style="color:#9aab97;font-size:11px;line-height:1.6;text-align:center">
              Este link es personal e intransferible. Expira en 72 horas.<br>
              Núcleo CERT es un servicio de certificación privada de fecha cierta e identidad de firmantes.<br>
              No reemplaza la escritura pública en los actos que la ley argentina exige dicha forma (art. 1017 CCCN).
            </p>
          </div>
        </div>
        """
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"Error email: {e}")
        return False

# ── RUTAS ESTÁTICAS ──
@app.route("/")
def landing():
    return send_from_directory("/var/www/nucleocert", "index.html")

@app.route("/certificar")
def certificar():
    return send_from_directory("/var/www/nucleocert", "certificar.html")

# ── API ──
def enviar_email_solicitante(destinatario, nombre_sol, numero_cert, tipo_tramite, partes, documento_nombre, fecha):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Núcleo CERT — Trámite iniciado: {numero_cert}"
        msg["From"] = f"Núcleo CERT <{GMAIL_USER}>"
        msg["To"] = destinatario
        partes_html = "".join([f"""
          <tr>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{p.get('nombre','')}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{p.get('dni_numero','')}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{p.get('rol','')}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0">{p.get('email','')}</td>
          </tr>""" for p in partes])
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f0f7f2;padding:32px">
          <div style="background:#fff;border-radius:12px;padding:32px;border:1px solid #e5e7eb">
            <div style="text-align:center;margin-bottom:24px">
              <h1 style="color:#2d9b5a;font-size:22px;margin:0">Núcleo CERT</h1>
              <p style="color:#5a6b57;font-size:13px;margin:4px 0">Certificación privada · Prueba permanente</p>
            </div>
            <p style="color:#374334;font-size:15px">Hola <strong>{nombre_sol}</strong>,</p>
            <p style="color:#374334;font-size:14px">Usted inició el trámite de certificación <strong>{tipo_tramite}</strong> con número:</p>
            <div style="background:#f0fdf4;border-radius:8px;padding:16px;text-align:center;margin:20px 0">
              <div style="font-size:13px;color:#5a6b57">Número de certificado</div>
              <div style="font-size:22px;font-weight:900;color:#2d9b5a">{numero_cert}</div>
              <div style="font-size:12px;color:#5a6b57;margin-top:4px">Fecha: {fecha}</div>
            </div>
            <p style="color:#374334;font-size:13px;font-weight:600">Documento certificado:</p>
            <p style="color:#5a6b57;font-size:13px">{documento_nombre}</p>
            <p style="color:#374334;font-size:13px;font-weight:600;margin-top:16px">Intervinientes:</p>
            <table style="width:100%;border-collapse:collapse;font-size:13px">
              <tr style="background:#f0fdf4">
                <th style="padding:8px;text-align:left">Nombre</th>
                <th style="padding:8px;text-align:left">DNI</th>
                <th style="padding:8px;text-align:left">Rol</th>
                <th style="padding:8px;text-align:left">Email</th>
              </tr>
              {partes_html}
            </table>
            <div style="margin-top:24px;padding:16px;background:#fef9c3;border-radius:8px;font-size:12px;color:#78400a">
              Una vez que todos los firmantes completen el proceso de verificación de identidad, el hash SHA-256 del documento será anclado en la blockchain de Núcleo NKL y Bitcoin como prueba permanente e inalterable.
            </div>
            <p style="color:#9aab97;font-size:11px;line-height:1.6;text-align:center;margin-top:20px">
              Núcleo CERT es un servicio de certificación privada de fecha cierta e identidad de firmantes.<br>
              No reemplaza la escritura pública en los actos que la ley argentina exige dicha forma (art. 1017 CCCN).
            </p>
          </div>
        </div>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"Error email solicitante: {e}")
        return False

@app.route("/api/paises", methods=["GET"])
def get_paises():
    conn = get_db()
    paises = conn.execute("SELECT * FROM paises ORDER BY estado DESC, nombre ASC").fetchall()
    conn.close()
    return jsonify([dict(p) for p in paises])

@app.route("/api/validar-minero", methods=["POST"])
def validar_minero():
    data = request.json
    username = data.get("username", "").strip().lower()
    api_key = data.get("api_key", "").strip()
    if not username or not api_key:
        return jsonify({"valido": False, "mensaje": "Usuario y key requeridos"}), 400
    try:
        conn = get_nkl_db()
        minero = conn.execute(
            "SELECT username, banned FROM miners WHERE username=? AND api_key=?",
            (username, api_key)
        ).fetchone()
        conn.close()
        if not minero:
            return jsonify({"valido": False, "mensaje": "Usuario o key incorrectos"}), 200
        if minero["banned"]:
            return jsonify({"valido": False, "mensaje": "Usuario suspendido"}), 200
        return jsonify({"valido": True, "username": minero["username"]}), 200
    except Exception as e:
        return jsonify({"valido": False, "mensaje": str(e)}), 500

@app.route("/api/tramites/nuevo", methods=["POST"])
def nuevo_tramite():
    data = request.json
    if not data:
        return jsonify({"error": "Sin datos"}), 400

    required = ["pais_codigo", "categoria", "tipo_tramite", "solicitante_nombre",
                "solicitante_doc", "solicitante_tipo", "solicitante_email", "partes"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Falta campo: {f}"}), 400

    conn = get_db()
    pais = conn.execute("SELECT * FROM paises WHERE codigo=? AND estado='activo'",
                        (data["pais_codigo"],)).fetchone()
    if not pais:
        conn.close()
        return jsonify({"error": "País no disponible"}), 400

    licencia_nkl_val = data.get("licencia_nkl", 0)
    licencia_nkl = int(licencia_nkl_val) if str(licencia_nkl_val).isdigit() else (1 if licencia_nkl_val else 0)
    n_partes = len(data["partes"])
    monto = 0 if licencia_nkl else pais["precio_certificado"] * n_partes
    fecha = datetime.utcnow().isoformat()
    year = datetime.utcnow().year

    c = conn.cursor()
    c.execute("""
        INSERT INTO tramites (pais_codigo, categoria, tipo_tramite, fecha_creacion,
            estado, modo, estado_pago, monto_total,
            solicitante_nombre, solicitante_doc, solicitante_tipo,
            solicitante_email, solicitante_telefono, licencia_nkl, minero_username)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data["pais_codigo"], data["categoria"], data["tipo_tramite"], fecha,
        "borrador", data.get("modo", "presencial"),
        "gratis" if licencia_nkl else "pendiente",
        monto,
        data["solicitante_nombre"], data["solicitante_doc"], data["solicitante_tipo"],
        data["solicitante_email"], data.get("solicitante_telefono", ""),
        licencia_nkl, data.get("minero_username", "")
    ))
    tramite_id = c.lastrowid
    numero_cert = f"CERT-{year}-{tramite_id:06d}"
    c.execute("UPDATE tramites SET numero_cert=? WHERE id=?", (numero_cert, tramite_id))

    links = []
    for parte in data["partes"]:
        link_uuid = str(uuid.uuid4())
        c.execute("""
            INSERT INTO partes (tramite_id, rol, nombre_completo, dni_numero, link_uuid, email)
            VALUES (?,?,?,?,?,?)
        """, (tramite_id, parte.get("rol","firmante"),
              parte.get("nombre",""), parte.get("dni",""),
              link_uuid, parte.get("email","")))
        links.append({
            "rol": parte.get("rol","firmante"),
            "nombre": parte.get("nombre",""),
            "email": parte.get("email",""),
            "link": f"https://nucleocert.com/firmar/{link_uuid}"
        })

    conn.commit()
    conn.close()

    # Si es gratis (minero/NKL) enviamos emails de inmediato
    emails_enviados = []
    if licencia_nkl:
        for p in links:
            if p.get("email"):
                ok = enviar_email(
                    p["email"], p["nombre"], p["link"],
                    numero_cert, data["tipo_tramite"], data["solicitante_nombre"]
                )
                emails_enviados.append({"email": p["email"], "enviado": ok})

    # Email al solicitante
    if licencia_nkl and data.get("solicitante_email"):
        fecha_str = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
        partes_data = [{"nombre": p["nombre"], "dni_numero": p.get("dni",""), "rol": p["rol"], "email": p.get("email","")} for p in data["partes"]]
        enviar_email_solicitante(
            data["solicitante_email"],
            data["solicitante_nombre"],
            numero_cert,
            data["tipo_tramite"],
            partes_data,
            data.get("documento_nombre", "Documento PDF"),
            fecha_str
        )
    return jsonify({
        "ok": True,
        "numero_cert": numero_cert,
        "tramite_id": tramite_id,
        "monto_total": monto,
        "estado_pago": "gratis" if licencia_nkl else "pendiente",
        "partes": links,
        "emails_enviados": emails_enviados
    }), 201

@app.route("/api/tramites/<numero_cert>/enviar-emails", methods=["POST"])
def enviar_emails_tramite(numero_cert):
    """Llamado después de confirmar el pago para enviar los links de firma"""
    conn = get_db()
    t = conn.execute("SELECT * FROM tramites WHERE numero_cert=?", (numero_cert,)).fetchone()
    if not t:
        conn.close()
        return jsonify({"error": "No encontrado"}), 404

    partes = conn.execute("SELECT * FROM partes WHERE tramite_id=?", (t["id"],)).fetchall()

    # marcar como pagado
    conn.execute("UPDATE tramites SET estado_pago='aprobado', emails_enviados=1 WHERE numero_cert=?",
                 (numero_cert,))
    conn.commit()
    conn.close()

    resultados = []
    for p in partes:
        link = f"https://nucleocert.com/firmar/{p['link_uuid']}"
        if p["email"]:
            ok = enviar_email(
                p["email"], p["nombre_completo"], link,
                numero_cert, dict(t)["tipo_tramite"], dict(t)["solicitante_nombre"]
            )
            resultados.append({"nombre": p["nombre_completo"], "email": p["email"], "enviado": ok})

    return jsonify({"ok": True, "resultados": resultados})

@app.route("/api/verificar/<numero_cert>", methods=["GET"])
def verificar_publico(numero_cert):
    conn = get_db()
    t = conn.execute("""
        SELECT numero_cert, tipo_tramite, fecha_certificacion, estado, hash_documento, pais_codigo
        FROM tramites WHERE numero_cert=?
    """, (numero_cert,)).fetchone()
    conn.close()
    if not t:
        return jsonify({"valido": False, "mensaje": "Certificado no encontrado"}), 404
    return jsonify({"valido": True, **dict(t)})

@app.route("/api/buscar-por-dni", methods=["POST"])
def buscar_por_dni():
    data = request.json
    dni = data.get("dni_numero", "").strip()
    nombre = data.get("nombre_completo", "").strip().upper()
    if not dni or not nombre:
        return jsonify({"error": "DNI y nombre requeridos"}), 400
    conn = get_db()
    partes = conn.execute("""
        SELECT p.rol, p.firma_timestamp, p.completado,
               t.numero_cert, t.tipo_tramite, t.fecha_creacion, t.estado, t.pais_codigo
        FROM partes p
        JOIN tramites t ON p.tramite_id = t.id
        WHERE p.dni_numero=? AND UPPER(p.nombre_completo) LIKE ?
        ORDER BY t.fecha_creacion DESC
    """, (dni, f"%{nombre}%")).fetchall()
    conn.close()
    return jsonify({"resultados": [dict(p) for p in partes]})
@app.route("/api/confirmar-tramite/<numero_cert>", methods=["GET"])
def confirmar_tramite(numero_cert):
    conn = get_db()
    t = conn.execute("SELECT * FROM tramites WHERE numero_cert=?", (numero_cert,)).fetchone()
    if not t:
        conn.close()
        return "<h2>Trámite no encontrado</h2>", 404
    conn.execute("UPDATE tramites SET estado='confirmado', fecha_certificacion=? WHERE numero_cert=?",
        (datetime.utcnow().isoformat(), numero_cert))
    conn.commit()
    conn.close()
    return f"""<html><body style="font-family:Arial;text-align:center;padding:60px">
        <h2 style="color:#2d9b5a">✅ Trámite confirmado</h2>
        <p>El trámite <strong>{numero_cert}</strong> fue confirmado.</p>
        <p style="color:#5a6b57;font-size:14px">El anclaje en blockchain NKL y Bitcoin se procesará en las próximas horas.</p>
        <a href="https://nucleocert.com" style="color:#2d9b5a">Volver a Núcleo CERT</a>
    </body></html>"""

@app.route("/api/anular-firma/<uuid>", methods=["GET"])
def anular_firma(uuid):
    solicitante_email = request.args.get("sol", "")
    conn = get_db()
    p = conn.execute("SELECT * FROM partes WHERE link_uuid=?", (uuid,)).fetchone()
    if not p:
        conn.close()
        return "<h2>Link no válido</h2>", 404
    tramite_id = p["tramite_id"]
    tramite = conn.execute("SELECT * FROM tramites WHERE id=?", (tramite_id,)).fetchone()
    # Resetear la firma
    conn.execute("UPDATE partes SET completado=0, firma_timestamp=NULL, sms_verificado=0 WHERE link_uuid=?", (uuid,))
    conn.commit()
    numero_cert = tramite["numero_cert"]
    firmante_nombre = p["nombre_completo"]
    firmante_email = p["email"]
    conn.close()
    # Notificar al firmante
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Núcleo CERT — Tu firma fue anulada ({numero_cert})"
        msg["From"] = f"Núcleo CERT <{GMAIL_USER}>"
        msg["To"] = firmante_email
        html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:32px">
          <h2 style="color:#dc2626">Firma anulada</h2>
          <p>Hola <strong>{firmante_nombre}</strong>,</p>
          <p>El solicitante del trámite <strong>{numero_cert}</strong> anuló tu firma porque los datos o fotos no coincidían.</p>
          <p>Por favor volvé a completar el proceso desde el link original que recibiste por email.</p>
          <p style="color:#9aab97;font-size:11px">Núcleo CERT — nucleocert.com</p>
        </div>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, firmante_email, msg.as_string())
    except Exception as e:
        print(f"Error email anulacion: {e}")
    return f"""<html><body style="font-family:Arial;text-align:center;padding:60px">
        <h2 style="color:#2d9b5a">✅ Firma anulada correctamente</h2>
        <p>Se notificó a <strong>{firmante_nombre}</strong> para que repita el proceso.</p>
        <p>Número de trámite: <strong>{numero_cert}</strong></p>
        <a href="https://nucleocert.com" style="color:#2d9b5a">Volver a Núcleo CERT</a>
    </body></html>"""

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5004, debug=False)

@app.route("/api/upload-documento", methods=["POST"])
def upload_documento():
    if 'archivo' not in request.files:
        return jsonify({"error": "Sin archivo"}), 400
    archivo = request.files['archivo']
    if not archivo.filename.endswith('.pdf'):
        return jsonify({"error": "Solo se aceptan archivos PDF"}), 400
    import hashlib, uuid as _uuid
    contenido = archivo.read()
    sha256 = hashlib.sha256(contenido).hexdigest()
    nombre = f"{_uuid.uuid4()}.pdf"
    ruta = f"/root/cert/uploads/{nombre}"
    with open(ruta, 'wb') as f:
        f.write(contenido)
    return jsonify({"ok": True, "hash": sha256, "archivo": nombre}), 201

@app.route("/api/firmar/<uuid>", methods=["GET"])
def get_firma(uuid):
    conn = get_db()
    p = conn.execute("SELECT * FROM partes WHERE link_uuid=?", (uuid,)).fetchone()
    if not p:
        conn.close()
        return jsonify({"ok": False, "error": "Link no válido o ya utilizado"}), 404
    t = conn.execute("SELECT * FROM tramites WHERE id=?", (p["tramite_id"],)).fetchone()
    conn.close()
    if p["completado"]:
        return jsonify({"ok": False, "error": "Esta firma ya fue completada"}), 400
    return jsonify({"ok": True, "parte": dict(p), "tramite": dict(t)})

@app.route("/api/firmar/<uuid>/validar-dni", methods=["POST"])
def validar_dni_firma(uuid):
    data = request.json
    conn = get_db()
    p = conn.execute("SELECT * FROM partes WHERE link_uuid=?", (uuid,)).fetchone()
    conn.close()
    if not p:
        return jsonify({"ok": False, "error": "Link no válido"}), 404
    dni_ingresado = str(data.get("dni_numero", "")).strip().replace(".", "").replace(" ", "")
    dni_registrado = str(p["dni_numero"]).strip().replace(".", "").replace(" ", "")
    if dni_registrado and dni_ingresado != dni_registrado:
        return jsonify({"ok": False, "error": "El DNI no coincide con el registrado para este trámite. Verificá los datos."}), 200
    return jsonify({"ok": True}), 200

@app.route("/api/firmar/<uuid>/enviar-sms", methods=["POST"])
def enviar_sms(uuid):
    data = request.json
    telefono = data.get("telefono", "").strip()
    if not telefono:
        return jsonify({"ok": False, "error": "Teléfono requerido"}), 400
    # Formatear número argentino
    if not telefono.startswith("+"):
        telefono = telefono.replace(" ", "").replace("-", "")
        if telefono.startswith("0"):
            telefono = telefono[1:]
        if not telefono.startswith("54"):
            telefono = "54" + telefono
        telefono = "+" + telefono
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        verification = client.verify.v2.services(TWILIO_VERIFY_SID).verifications.create(
            to=telefono,
            channel="sms"
        )
        return jsonify({"ok": True, "mensaje": "SMS enviado", "status": verification.status})
    except Exception as e:
        print(f"Error Twilio enviar: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/firmar/<uuid>/completar", methods=["POST"])
def completar_firma(uuid):
    data = request.json
    conn = get_db()
    p = conn.execute("SELECT * FROM partes WHERE link_uuid=?", (uuid,)).fetchone()
    if not p:
        conn.close()
        return jsonify({"ok": False, "error": "Link no válido"}), 404
    if p["completado"]:
        conn.close()
        return jsonify({"ok": False, "error": "Ya completada"}), 400
    # Validar DNI contra el registrado por el solicitante
    dni_ingresado = str(data.get("dni_numero", "")).strip().replace(".", "").replace(" ", "")
    dni_registrado = str(p["dni_numero"]).strip().replace(".", "").replace(" ", "")
    if dni_registrado and dni_ingresado != dni_registrado:
        conn.close()
        return jsonify({"ok": False, "error": f"El DNI ingresado no coincide con el registrado para este trámite. Verificá los datos e intentá de nuevo."}), 400
    import os as _os
    carpeta = f"/root/cert/uploads/{uuid}"
    _os.makedirs(carpeta, exist_ok=True)
    # Guardar imágenes
    for campo in ["dni_frente","dni_dorso","selfie","video"]:
        val = data.get(campo,"")
        if val and "," in val:
            import base64 as _b64
            ext = "jpg" if campo != "video" else "webm"
            raw = _b64.b64decode(val.split(",")[1])
            with open(f"{carpeta}/{campo}.{ext}", "wb") as f:
                f.write(raw)
    # Verificar código SMS con Twilio
    telefono = data.get("telefono", "").strip()
    sms_codigo = data.get("sms_codigo", "").strip()
    if telefono and sms_codigo and TWILIO_ACCOUNT_SID:
        if not telefono.startswith("+"):
            telefono = telefono.replace(" ", "").replace("-", "")
            if telefono.startswith("0"):
                telefono = telefono[1:]
            if not telefono.startswith("54"):
                telefono = "54" + telefono
            telefono = "+" + telefono
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            check = client.verify.v2.services(TWILIO_VERIFY_SID).verification_checks.create(
                to=telefono,
                code=sms_codigo
            )
            if check.status != "approved":
                conn.close()
                return jsonify({"ok": False, "error": "Código SMS incorrecto. Verificá e intentá de nuevo."}), 400
        except Exception as e:
            print(f"Error Twilio verificar: {e}")
            conn.close()
            return jsonify({"ok": False, "error": "Error al verificar el código SMS."}), 500
    conn.execute("""UPDATE partes SET completado=1, nombre_completo=?, dni_numero=?,
        firma_timestamp=?, sms_verificado=1 WHERE link_uuid=?""",
        (data.get("nombre_completo",""), data.get("dni_numero",""),
         datetime.utcnow().isoformat(), uuid))
    conn.commit()
    # Verificar si todos firmaron
    tramite_id = p["tramite_id"]
    total = conn.execute("SELECT COUNT(*) FROM partes WHERE tramite_id=?", (tramite_id,)).fetchone()[0]
    completados = conn.execute("SELECT COUNT(*) FROM partes WHERE tramite_id=? AND completado=1", (tramite_id,)).fetchone()[0]
    numero_cert = conn.execute("SELECT numero_cert FROM tramites WHERE id=?", (tramite_id,)).fetchone()[0]
    tramite = conn.execute("SELECT * FROM tramites WHERE id=?", (tramite_id,)).fetchone()
    conn.close()
    # Enviar email al solicitante con fotos del firmante
    try:
        import base64 as _b64
        solicitante_email = tramite["solicitante_email"]
        solicitante_nombre = tramite["solicitante_nombre"]
        firmante_nombre = data.get("nombre_completo", p["nombre_completo"])
        firmante_dni = data.get("dni_numero", p["dni_numero"])
        firmante_rol = p["rol"]
        fecha_str = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
        # Leer fotos guardadas
        def foto_b64(campo, ext):
            path = f"{carpeta}/{campo}.{ext}"
            if _os.path.exists(path):
                with open(path, "rb") as f:
                    return _b64.b64encode(f.read()).decode()
            return None
        frente = foto_b64("dni_frente", "jpg")
        dorso = foto_b64("dni_dorso", "jpg")
        selfie = foto_b64("selfie", "jpg")
        def img_tag(b64, label):
            if b64:
                return f'<div style="margin-bottom:16px"><div style="font-size:.78rem;font-weight:600;color:#5a6b57;margin-bottom:6px">{label}</div><img src="data:image/jpeg;base64,{b64}" style="width:100%;max-width:320px;border-radius:8px;border:1px solid #e5e7eb"></div>'
            return f'<div style="color:#9aab97;font-size:.82rem">{label}: no disponible</div>'
        from email.mime.image import MIMEImage
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Núcleo CERT — {firmante_nombre} completó su firma ({numero_cert})"
        msg["From"] = f"Núcleo CERT <{GMAIL_USER}>"
        msg["To"] = solicitante_email
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f0f7f2;padding:32px">
          <div style="background:#fff;border-radius:12px;padding:32px;border:1px solid #e5e7eb">
            <div style="text-align:center;margin-bottom:24px">
              <h1 style="color:#2d9b5a;font-size:22px;margin:0">Núcleo CERT</h1>
              <p style="color:#5a6b57;font-size:13px;margin:4px 0">Verificación de identidad del firmante</p>
            </div>
            <p style="color:#374334;font-size:15px">Hola <strong>{solicitante_nombre}</strong>,</p>
            <p style="color:#374334;font-size:14px"><strong>{firmante_nombre}</strong> ({firmante_rol}) completó su proceso de verificación de identidad para el trámite <strong>{numero_cert}</strong>.</p>
            <div style="background:#f0fdf4;border-radius:8px;padding:16px;margin:20px 0">
              <div style="font-size:13px;color:#5a6b57">Firmante</div>
              <div style="font-size:15px;font-weight:700;color:#1a2e1a">{firmante_nombre}</div>
              <div style="font-size:13px;color:#5a6b57">DNI: {firmante_dni} — Rol: {firmante_rol}</div>
              <div style="font-size:12px;color:#9aab97;margin-top:4px">Fecha: {fecha_str}</div>
            </div>
            <p style="color:#374334;font-size:13px;font-weight:600">Por favor verificá que las fotos correspondan a la persona indicada:</p>
            <p style="color:#374334;font-size:13px">Las fotos del DNI y selfie se encuentran adjuntas a este email.</p>
            <div style="text-align:center;margin:24px 0">
              <a href="https://nucleocert.com/api/anular-firma/{uuid}?sol={solicitante_email}" style="background:#dc2626;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-size:14px;font-weight:700;display:inline-block;margin-right:12px">❌ Anular esta firma</a>
            </div>
            <div style="background:#fef9c3;border-radius:8px;padding:14px;font-size:13px;color:#78400a;margin-top:8px">
              Si las fotos no corresponden a <strong>{firmante_nombre}</strong> o el DNI no es válido, hacé clic en "Anular esta firma". El firmante recibirá una notificación para repetir el proceso.
            </div>
            <p style="color:#9aab97;font-size:11px;line-height:1.6;text-align:center;margin-top:20px">
              Núcleo CERT — nucleocert.com<br>
              No reemplaza la escritura pública en los actos que la ley argentina exige dicha forma (art. 1017 CCCN).
            </p>
          </div>
        </div>"""
        msg.attach(MIMEText(html, "html"))
        # Adjuntar fotos
        for campo, label in [("dni_frente","DNI_frente"), ("dni_dorso","DNI_dorso"), ("selfie","Selfie")]:
            path = f"{carpeta}/{campo}.jpg"
            if _os.path.exists(path):
                with open(path, "rb") as f:
                    img = MIMEImage(f.read(), _subtype="jpeg")
                    img.add_header("Content-Disposition", "attachment", filename=f"{label}_{firmante_nombre.replace(' ','_')}.jpg")
                    msg.attach(img)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, solicitante_email, msg.as_string())
        print(f"Email fotos enviado a {solicitante_email}")
    except Exception as e:
        print(f"Error email fotos solicitante: {e}")
    # Si todos firmaron, mandar email de confirmacion al solicitante
    if total == completados:
        try:
            confirm_url = f"https://nucleocert.com/api/confirmar-tramite/{numero_cert}?sol={tramite['solicitante_email']}"
            msg2 = MIMEMultipart("alternative")
            msg2["Subject"] = f"Núcleo CERT — ¡Todos firmaron! Confirmá el trámite {numero_cert}"
            msg2["From"] = f"Núcleo CERT <{GMAIL_USER}>"
            msg2["To"] = tramite["solicitante_email"]
            html2 = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f0f7f2;padding:32px">
              <div style="background:#fff;border-radius:12px;padding:32px;border:1px solid #e5e7eb">
                <div style="text-align:center;margin-bottom:24px">
                  <h1 style="color:#2d9b5a;font-size:22px;margin:0">Núcleo CERT</h1>
                </div>
                <p style="color:#374334;font-size:15px">Hola <strong>{tramite['solicitante_nombre']}</strong>,</p>
                <p style="color:#374334;font-size:14px">Todos los firmantes del trámite <strong>{numero_cert}</strong> completaron su verificación de identidad.</p>
                <div style="background:#f0fdf4;border-radius:8px;padding:16px;text-align:center;margin:20px 0">
                  <div style="font-size:13px;color:#5a6b57">Trámite</div>
                  <div style="font-size:20px;font-weight:900;color:#2d9b5a">{numero_cert}</div>
                  <div style="font-size:13px;color:#5a6b57;margin-top:4px">{tramite['tipo_tramite']} — {total} firmante{'s' if total > 1 else ''}</div>
                </div>
                <p style="color:#374334;font-size:13px">Si verificaste las identidades de todos los firmantes y estás conforme, confirmá el trámite para anclar el documento en blockchain:</p>
                <div style="text-align:center;margin:24px 0">
                  <a href="{confirm_url}" style="background:#2d9b5a;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-size:16px;font-weight:700;display:inline-block">✅ Confirmar y anclar en blockchain</a>
                </div>
                <p style="color:#9aab97;font-size:11px;line-height:1.6;text-align:center;margin-top:20px">
                  Núcleo CERT — nucleocert.com<br>
                  No reemplaza la escritura pública en los actos que la ley argentina exige dicha forma (art. 1017 CCCN).
                </p>
              </div>
            </div>"""
            msg2.attach(MIMEText(html2, "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(GMAIL_USER, GMAIL_PASS)
                server.sendmail(GMAIL_USER, tramite["solicitante_email"], msg2.as_string())
            print(f"Email confirmacion enviado a {tramite['solicitante_email']}")
        except Exception as e:
            print(f"Error email confirmacion: {e}")
    return jsonify({"ok": True, "numero_cert": numero_cert, "total": total, "completados": completados})
