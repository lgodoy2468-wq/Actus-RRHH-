#!/usr/bin/env python3
"""
Actus Postulantes - Sistema privado de gestión de candidatos
Actus & Asociados S.A.
Aplicación completa, independiente, con base de datos SQLite persistente.
"""

import os
import re
import json
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, session, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

# ──────────────────────────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────────────────────────
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "actus-postulantes-secreto-cambiar-en-produccion-2026")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "instance", "actus.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 8  # 8 horas

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Debés iniciar sesión para continuar."
login_manager.login_message_category = "warning"

# ──────────────────────────────────────────────────────────────
# Modelos
# ──────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default="reclutador")  # admin | reclutador
    activo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.rol == "admin"


class Corporativo(db.Model):
    __tablename__ = "corporativos"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, unique=True)
    activo = db.Column(db.Boolean, default=True)
    observaciones = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Vacante(db.Model):
    __tablename__ = "vacantes"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    corporativo_id = db.Column(db.Integer, db.ForeignKey("corporativos.id"), nullable=True)
    estado = db.Column(db.String(30), default="activa")  # activa | cerrada | pausada
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    corporativo = db.relationship("Corporativo", backref="vacantes")


class Postulante(db.Model):
    __tablename__ = "postulantes"
    id = db.Column(db.Integer, primary_key=True)
    cedula = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nombre_completo = db.Column(db.String(200), nullable=False)
    telefono = db.Column(db.String(40))
    direccion = db.Column(db.String(300))
    estado = db.Column(db.String(40), default="pendiente")  # pendiente | contactado | en_proceso | descartado
    observaciones = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contactos = db.relationship("Contacto", backref="postulante", lazy="dynamic", cascade="all, delete-orphan")
    referencias = db.relationship("ReferenciaLaboral", backref="postulante", lazy="dynamic", cascade="all, delete-orphan")
    expectativas = db.relationship("ExpectativaSalarial", backref="postulante", lazy="dynamic", cascade="all, delete-orphan")
    postulaciones = db.relationship("Postulacion", backref="postulante", lazy="dynamic", cascade="all, delete-orphan")


class Postulacion(db.Model):
    __tablename__ = "postulaciones"
    id = db.Column(db.Integer, primary_key=True)
    postulante_id = db.Column(db.Integer, db.ForeignKey("postulantes.id"), nullable=False)
    vacante_id = db.Column(db.Integer, db.ForeignKey("vacantes.id"), nullable=True)
    corporativo_id = db.Column(db.Integer, db.ForeignKey("corporativos.id"), nullable=True)
    estado = db.Column(db.String(40), default="activo")
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    responsable_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    notas = db.Column(db.Text)

    vacante = db.relationship("Vacante")
    corporativo = db.relationship("Corporativo")


class Contacto(db.Model):
    __tablename__ = "contactos"
    id = db.Column(db.Integer, primary_key=True)
    postulante_id = db.Column(db.Integer, db.ForeignKey("postulantes.id"), nullable=False)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)
    medio = db.Column(db.String(40), default="whatsapp")  # whatsapp | telefono | email | presencial
    resultado = db.Column(db.String(100))
    responsable_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    corporativo_id = db.Column(db.Integer, db.ForeignKey("corporativos.id"), nullable=True)
    proximo_paso = db.Column(db.String(200))
    observaciones = db.Column(db.Text)

    responsable = db.relationship("User")
    corporativo = db.relationship("Corporativo")


class ReferenciaLaboral(db.Model):
    __tablename__ = "referencias_laborales"
    id = db.Column(db.Integer, primary_key=True)
    postulante_id = db.Column(db.Integer, db.ForeignKey("postulantes.id"), nullable=False)
    mala_referencia = db.Column(db.String(20), default="No")  # Si | No | Pendiente
    motivo = db.Column(db.Text)
    empresa_relacionada = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    responsable_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    observaciones = db.Column(db.Text)

    responsable = db.relationship("User")


class ExpectativaSalarial(db.Model):
    __tablename__ = "expectativas_salariales"
    id = db.Column(db.Integer, primary_key=True)
    postulante_id = db.Column(db.Integer, db.ForeignKey("postulantes.id"), nullable=False)
    importe = db.Column(db.Float, nullable=False)
    moneda = db.Column(db.String(10), default="PYG")
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    responsable_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    responsable = db.relationship("User")


class Actividad(db.Model):
    __tablename__ = "actividad"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    accion = db.Column(db.String(100), nullable=False)
    tipo_registro = db.Column(db.String(50))
    id_registro = db.Column(db.Integer)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)
    resultado = db.Column(db.String(50), default="ok")
    detalle = db.Column(db.Text)

    usuario = db.relationship("User")


class Configuracion(db.Model):
    __tablename__ = "configuracion"
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True)
    valor = db.Column(db.Text)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("No tenés permisos de administrador.", "danger")
            return redirect(url_for("panel"))
        return f(*args, **kwargs)
    return decorated


def normalizar_cedula(cedula: str) -> str:
    """Quita puntos, espacios y guiones. Solo dígitos."""
    if not cedula:
        return ""
    return re.sub(r"[^\d]", "", cedula.strip())


def formatear_cedula(cedula: str) -> str:
    """Formato paraguayo aproximado: 1.234.567"""
    n = normalizar_cedula(cedula)
    if not n:
        return ""
    # Agrupa de derecha a izquierda cada 3 dígitos
    partes = []
    while n:
        partes.append(n[-3:])
        n = n[:-3]
    return ".".join(reversed(partes))


def registrar_actividad(accion, tipo=None, id_reg=None, resultado="ok", detalle=None):
    try:
        act = Actividad(
            usuario_id=current_user.id if current_user.is_authenticated else None,
            accion=accion,
            tipo_registro=tipo,
            id_registro=id_reg,
            resultado=resultado,
            detalle=detalle
        )
        db.session.add(act)
        db.session.commit()
    except Exception:
        db.session.rollback()


def parsear_importe(texto: str):
    """Convierte textos como '3.000.000', '3 millones', '1789000' a número."""
    if not texto:
        return None
    t = texto.lower().strip()
    # millones
    m = re.search(r"([\d.,]+)\s*(?:millones?|mill[oó]n)", t)
    if m:
        num = m.group(1).replace(".", "").replace(",", ".")
        try:
            return float(num) * 1_000_000
        except ValueError:
            pass
    # solo números con puntos de miles
    limpio = re.sub(r"[^\d]", "", t)
    if limpio:
        try:
            return float(limpio)
        except ValueError:
            pass
    return None


# ──────────────────────────────────────────────────────────────
# Motor de interpretación de lenguaje natural (sin API externa)
# ──────────────────────────────────────────────────────────────
def interpretar_texto(texto: str) -> dict:
    """
    Extrae campos estructurados de una frase natural.
    Reglas estrictas: no inventa datos, no confunde corporativo con persona de contacto.
    """
    resultado = {
        "nombre_completo": None,
        "cedula": None,
        "vacante": None,
        "corporativo": None,
        "contacto_persona": None,
        "telefono": None,
        "expectativa_importe": None,
        "expectativa_moneda": "PYG",
        "mala_referencia": "No",
        "motivo_referencia": None,
        "empresa_referencia": None,
        "estado": "pendiente",
        "ya_contactado": False,
        "observaciones": None,
        "campos_detectados": [],
        "advertencias": []
    }

    if not texto or not texto.strip():
        return resultado

    t = texto.strip()

    # ── Cédula ──
    # Patrones: 7.648.300  |  7648300  |  cédula 5.016.942
    ced_match = re.search(
        r"(?:c[eé]dula|ci|documento|n[uú]mero\s+de\s+c[eé]dula)[:\s]*([0-9]{1,3}(?:[.\s]?[0-9]{3}){1,3})",
        t, re.IGNORECASE
    )
    if not ced_match:
        ced_match = re.search(r"\b([0-9]{6,10})\b", t)
    if ced_match:
        resultado["cedula"] = normalizar_cedula(ced_match.group(1))
        resultado["campos_detectados"].append("cedula")

    # ── Nombre completo ──
    # Busca después de "nombre de", "llamado", "agregar a", etc.
    nom_patterns = [
        r"(?:nombre\s+de|llamad[oa]|agregar\s+a|a[ñn]adir\s+a|postulante\s+)([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})",
        r"(?:con\s+nombre\s+de)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})",
        r"^([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})\s*,?\s*(?:c[eé]dula|ci)",
    ]
    for pat in nom_patterns:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            resultado["nombre_completo"] = m.group(1).strip()
            resultado["campos_detectados"].append("nombre_completo")
            break

    # Si no encontró, intenta el primer nombre propio de 2-4 palabras
    if not resultado["nombre_completo"]:
        m = re.search(r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})\b", t)
        if m:
            posible = m.group(1)
            # Evitar que tome "Junior Godoy" si es corporativo
            if "corporativo" not in t.lower()[max(0, t.lower().find(posible.lower())-30):t.lower().find(posible.lower())+len(posible)+10]:
                resultado["nombre_completo"] = posible
                resultado["campos_detectados"].append("nombre_completo")

    # ── Vacante ──
    vac_patterns = [
        r"(?:vacante|vacancia|puesto|cargo)\s+(?:de\s+)?([a-záéíóúñ\s]{3,40}?)(?:\s+(?:ya|para|del|de\s+la|con|y|,|\.|$))",
        r"para\s+(?:la\s+)?(?:vacante|vacancia|puesto)\s+(?:de\s+)?([a-záéíóúñ\s]{3,40}?)(?:\s+(?:ya|del|de|con|y|,|\.|$))",
        r"para\s+(?:el\s+)?([a-záéíóúñ]{4,30})\s+(?:ya|del|de\s+la)",
    ]
    for pat in vac_patterns:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            vac = m.group(1).strip().rstrip(".,")
            if vac and len(vac) > 2:
                resultado["vacante"] = vac
                resultado["campos_detectados"].append("vacante")
                break

    # ── Corporativo / Empresa ──
    corp_patterns = [
        r"(?:corporativo|empresa|desde\s+el\s+corporativo)\s+(?:de\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})",
        r"(?:corporativo|empresa)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})",
    ]
    for pat in corp_patterns:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            corp = m.group(1).strip()
            # No tomar nombres de personas de contacto
            if corp and "contact" not in corp.lower():
                resultado["corporativo"] = corp
                resultado["campos_detectados"].append("corporativo")
                break

    # ── Persona de contacto ──
    cont_patterns = [
        r"(?:lo\s+contact[oó]|contact[oó]|persona\s+de\s+contacto|contactado\s+por)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})",
        r"(?:contactado\s+por)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})",
    ]
    for pat in cont_patterns:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            resultado["contacto_persona"] = m.group(1).strip()
            resultado["campos_detectados"].append("contacto_persona")
            break

    # ── Ya contactado ──
    if re.search(r"\b(ya\s+fue\s+contactado|ya\s+contactado|fue\s+contactado)\b", t, re.IGNORECASE):
        resultado["ya_contactado"] = True
        resultado["estado"] = "contactado"
        resultado["campos_detectados"].append("estado")

    # ── Expectativa salarial ──
    sal_patterns = [
        r"(?:expectativa\s+salarial|salario|sueldo|pretende|pide)\s+(?:de\s+)?([\d.,]+)\s*(?:guaran[ií]es|gs\.?|pyg)?",
        r"([\d.,]+)\s*(?:guaran[ií]es|gs\.?)\b",
        r"(?:de\s+)?([\d.,]+)\s*(?:millones?)\s*(?:de\s+)?(?:guaran[ií]es|gs\.?)?",
    ]
    for pat in sal_patterns:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            imp = parsear_importe(m.group(0))
            if imp:
                resultado["expectativa_importe"] = imp
                resultado["campos_detectados"].append("expectativa_importe")
                break

    # ── Mala referencia ──
    if re.search(r"\b(mala\s+referencia|tiene\s+mala\s+referencia|con\s+mala\s+referencia)\b", t, re.IGNORECASE):
        resultado["mala_referencia"] = "Si"
        resultado["campos_detectados"].append("mala_referencia")
        # Motivo
        mot = re.search(r"(?:por|debido\s+a|motivo)\s+([^.]+)", t, re.IGNORECASE)
        if mot:
            resultado["motivo_referencia"] = mot.group(1).strip()
        # Empresa de la referencia
        emp_ref = re.search(r"(?:de\s+(?:la\s+)?empresa|empresa)\s+([A-ZÁÉÍÓÚÑ0-9][a-záéíóúñ0-9\s]{2,40})", t, re.IGNORECASE)
        if emp_ref:
            resultado["empresa_referencia"] = emp_ref.group(1).strip()

    # Advertencias
    if not resultado["nombre_completo"]:
        resultado["advertencias"].append("No se detectó nombre completo.")
    if not resultado["cedula"]:
        resultado["advertencias"].append("No se detectó número de cédula.")
    if resultado["vacante"] and not resultado["corporativo"]:
        resultado["advertencias"].append("Se detectó vacante pero no corporativo.")

    return resultado


# ──────────────────────────────────────────────────────────────
# Rutas de autenticación
# ──────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("panel"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        password = request.form.get("password", "")
        modo = request.form.get("modo", "nombre")  # nombre | individual

        user = None
        if modo == "individual":
            # Login por email (usuario individual)
            email = request.form.get("email", "").strip().lower()
            user = User.query.filter_by(email=email, activo=True).first()
        else:
            # Login por nombre + contraseña de rol
            user = User.query.filter(
                db.func.lower(User.nombre) == nombre.lower(),
                User.activo == True
            ).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            session.permanent = True
            registrar_actividad("login", resultado="ok")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("panel"))
        else:
            flash("Nombre o contraseña incorrectos.", "danger")
            registrar_actividad("login_fallido", resultado="error", detalle=nombre)

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    registrar_actividad("logout")
    logout_user()
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("login"))


# ──────────────────────────────────────────────────────────────
# Panel principal
# ──────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def panel():
    total_postulantes = Postulante.query.count()
    contactados = Postulante.query.filter_by(estado="contactado").count()
    pendientes = Postulante.query.filter_by(estado="pendiente").count()
    malas_ref = ReferenciaLaboral.query.filter_by(mala_referencia="Si").count()
    vacantes_act = Vacante.query.filter_by(estado="activa").count()

    recientes = Postulante.query.order_by(Postulante.created_at.desc()).limit(5).all()
    ultimos_eventos = Actividad.query.order_by(Actividad.fecha_hora.desc()).limit(8).all()

    return render_template(
        "panel.html",
        total_postulantes=total_postulantes,
        contactados=contactados,
        pendientes=pendientes,
        malas_ref=malas_ref,
        vacantes_act=vacantes_act,
        recientes=recientes,
        ultimos_eventos=ultimos_eventos
    )


# ──────────────────────────────────────────────────────────────
# Postulantes
# ──────────────────────────────────────────────────────────────
@app.route("/postulantes")
@login_required
def postulantes():
    q = request.args.get("q", "").strip()
    estado = request.args.get("estado", "")
    vacante_id = request.args.get("vacante", "")
    solo_mala = request.args.get("mala") == "1"

    query = Postulante.query

    if q:
        ced = normalizar_cedula(q)
        if ced:
            query = query.filter(
                db.or_(
                    Postulante.cedula.contains(ced),
                    Postulante.nombre_completo.ilike(f"%{q}%")
                )
            )
        else:
            query = query.filter(Postulante.nombre_completo.ilike(f"%{q}%"))

    if estado:
        query = query.filter_by(estado=estado)

    if solo_mala:
        query = query.join(ReferenciaLaboral).filter(ReferenciaLaboral.mala_referencia == "Si")

    lista = query.order_by(Postulante.created_at.desc()).all()
    vacantes = Vacante.query.filter_by(estado="activa").all()

    return render_template("postulantes.html", lista=lista, vacantes=vacantes, q=q, estado=estado)


@app.route("/postulantes/nuevo", methods=["GET", "POST"])
@login_required
def nuevo_postulante():
    if request.method == "POST":
        cedula = normalizar_cedula(request.form.get("cedula", ""))
        nombre = request.form.get("nombre_completo", "").strip()
        telefono = request.form.get("telefono", "").strip()
        vacante_id = request.form.get("vacante_id") or None
        corporativo_id = request.form.get("corporativo_id") or None
        estado = request.form.get("estado", "pendiente")
        expectativa = request.form.get("expectativa", "").strip()
        mala_ref = request.form.get("mala_referencia", "No")
        motivo_ref = request.form.get("motivo_referencia", "").strip()
        empresa_ref = request.form.get("empresa_referencia", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        errores = []
        if not cedula:
            errores.append("La cédula es obligatoria.")
        if not nombre:
            errores.append("El nombre completo es obligatorio.")

        existente = Postulante.query.filter_by(cedula=cedula).first()
        if existente:
            flash(f"Ya existe un postulante con cédula {formatear_cedula(cedula)}. Se abrió su ficha.", "warning")
            return redirect(url_for("ver_postulante", id=existente.id))

        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template(
                "nuevo_postulante.html",
                vacantes=Vacante.query.filter_by(estado="activa").all(),
                corporativos=Corporativo.query.filter_by(activo=True).all(),
                form=request.form
            )

        p = Postulante(
            cedula=cedula,
            nombre_completo=nombre,
            telefono=telefono or None,
            estado=estado,
            observaciones=observaciones or None,
            created_by=current_user.id,
            updated_by=current_user.id
        )
        db.session.add(p)
        db.session.flush()

        # Postulación
        if vacante_id or corporativo_id:
            post = Postulacion(
                postulante_id=p.id,
                vacante_id=int(vacante_id) if vacante_id else None,
                corporativo_id=int(corporativo_id) if corporativo_id else None,
                responsable_id=current_user.id,
                estado="activo"
            )
            db.session.add(post)

        # Expectativa
        if expectativa:
            imp = parsear_importe(expectativa)
            if imp:
                exp = ExpectativaSalarial(
                    postulante_id=p.id,
                    importe=imp,
                    moneda="PYG",
                    responsable_id=current_user.id
                )
                db.session.add(exp)

        # Referencia
        if mala_ref == "Si":
            ref = ReferenciaLaboral(
                postulante_id=p.id,
                mala_referencia="Si",
                motivo=motivo_ref or None,
                empresa_relacionada=empresa_ref or None,
                responsable_id=current_user.id
            )
            db.session.add(ref)

        db.session.commit()
        registrar_actividad("crear_postulante", "postulante", p.id)
        flash(f"Postulante {nombre} registrado correctamente.", "success")
        return redirect(url_for("ver_postulante", id=p.id))

    return render_template(
        "nuevo_postulante.html",
        vacantes=Vacante.query.filter_by(estado="activa").all(),
        corporativos=Corporativo.query.filter_by(activo=True).all()
    )


@app.route("/postulantes/ia", methods=["GET", "POST"])
@login_required
def agregar_con_ia():
    if request.method == "POST":
        accion = request.form.get("accion", "interpretar")

        if accion == "interpretar":
            texto = request.form.get("texto", "").strip()
            if not texto:
                flash("Escribí o dictá los datos del postulante.", "warning")
                return render_template("agregar_ia.html")

            datos = interpretar_texto(texto)
            # Buscar coincidencias de vacante y corporativo existentes
            vacantes = Vacante.query.filter_by(estado="activa").all()
            corporativos = Corporativo.query.filter_by(activo=True).all()

            vacante_match = None
            if datos["vacante"]:
                for v in vacantes:
                    if datos["vacante"].lower() in v.nombre.lower() or v.nombre.lower() in datos["vacante"].lower():
                        vacante_match = v
                        break

            corp_match = None
            if datos["corporativo"]:
                for c in corporativos:
                    if datos["corporativo"].lower() in c.nombre.lower() or c.nombre.lower() in datos["corporativo"].lower():
                        corp_match = c
                        break

            return render_template(
                "agregar_ia.html",
                texto_original=texto,
                datos=datos,
                vacante_match=vacante_match,
                corp_match=corp_match,
                vacantes=vacantes,
                corporativos=corporativos,
                modo="confirmacion"
            )

        elif accion == "confirmar":
            # Guardar definitivo
            cedula = normalizar_cedula(request.form.get("cedula", ""))
            nombre = request.form.get("nombre_completo", "").strip()
            if not cedula or not nombre:
                flash("Cédula y nombre son obligatorios.", "danger")
                return redirect(url_for("agregar_con_ia"))

            existente = Postulante.query.filter_by(cedula=cedula).first()
            if existente:
                flash(f"Ya existe postulante con esa cédula. Se abrió su ficha.", "warning")
                return redirect(url_for("ver_postulante", id=existente.id))

            p = Postulante(
                cedula=cedula,
                nombre_completo=nombre,
                telefono=request.form.get("telefono") or None,
                estado=request.form.get("estado", "pendiente"),
                observaciones=request.form.get("observaciones") or None,
                created_by=current_user.id,
                updated_by=current_user.id
            )
            db.session.add(p)
            db.session.flush()

            vacante_id = request.form.get("vacante_id") or None
            corporativo_id = request.form.get("corporativo_id") or None
            if vacante_id or corporativo_id:
                post = Postulacion(
                    postulante_id=p.id,
                    vacante_id=int(vacante_id) if vacante_id else None,
                    corporativo_id=int(corporativo_id) if corporativo_id else None,
                    responsable_id=current_user.id
                )
                db.session.add(post)

            imp = request.form.get("expectativa_importe")
            if imp:
                try:
                    exp = ExpectativaSalarial(
                        postulante_id=p.id,
                        importe=float(imp),
                        moneda="PYG",
                        responsable_id=current_user.id
                    )
                    db.session.add(exp)
                except ValueError:
                    pass

            if request.form.get("mala_referencia") == "Si":
                ref = ReferenciaLaboral(
                    postulante_id=p.id,
                    mala_referencia="Si",
                    motivo=request.form.get("motivo_referencia") or None,
                    empresa_relacionada=request.form.get("empresa_referencia") or None,
                    responsable_id=current_user.id
                )
                db.session.add(ref)

            db.session.commit()
            registrar_actividad("crear_postulante_ia", "postulante", p.id)
            flash(f"Postulante {nombre} registrado correctamente.", "success")
            return redirect(url_for("ver_postulante", id=p.id))

    return render_template("agregar_ia.html", modo="entrada")


@app.route("/postulantes/<int:id>")
@login_required
def ver_postulante(id):
    p = db.session.get(Postulante, id)
    if not p:
        abort(404)
    return render_template("ver_postulante.html", p=p)


@app.route("/postulantes/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_postulante(id):
    p = db.session.get(Postulante, id)
    if not p:
        abort(404)

    if request.method == "POST":
        p.nombre_completo = request.form.get("nombre_completo", p.nombre_completo).strip()
        p.telefono = request.form.get("telefono") or None
        p.estado = request.form.get("estado", p.estado)
        p.observaciones = request.form.get("observaciones") or None
        p.updated_by = current_user.id
        p.updated_at = datetime.utcnow()
        db.session.commit()
        registrar_actividad("editar_postulante", "postulante", p.id)
        flash("Datos actualizados.", "success")
        return redirect(url_for("ver_postulante", id=p.id))

    return render_template("editar_postulante.html", p=p)


# ──────────────────────────────────────────────────────────────
# Buscador rápido por cédula
# ──────────────────────────────────────────────────────────────
@app.route("/buscar")
@login_required
def buscar():
    cedula = request.args.get("cedula", "").strip()
    if not cedula:
        return render_template("buscar.html")

    n = normalizar_cedula(cedula)
    p = Postulante.query.filter_by(cedula=n).first()
    if p:
        return redirect(url_for("ver_postulante", id=p.id))
    flash(f"No se encontró ningún postulante con cédula {formatear_cedula(cedula)}.", "warning")
    return render_template("buscar.html", cedula=cedula)


# ──────────────────────────────────────────────────────────────
# Vacantes
# ──────────────────────────────────────────────────────────────
@app.route("/vacantes")
@login_required
def vacantes():
    lista = Vacante.query.order_by(Vacante.created_at.desc()).all()
    return render_template("vacantes.html", lista=lista)


@app.route("/vacantes/nueva", methods=["GET", "POST"])
@login_required
def nueva_vacante():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("El nombre de la vacante es obligatorio.", "danger")
            return redirect(url_for("nueva_vacante"))
        v = Vacante(
            nombre=nombre,
            descripcion=request.form.get("descripcion") or None,
            corporativo_id=request.form.get("corporativo_id") or None,
            estado="activa",
            created_by=current_user.id
        )
        db.session.add(v)
        db.session.commit()
        registrar_actividad("crear_vacante", "vacante", v.id)
        flash("Vacante creada.", "success")
        return redirect(url_for("vacantes"))
    return render_template(
        "nueva_vacante.html",
        corporativos=Corporativo.query.filter_by(activo=True).all()
    )


# ──────────────────────────────────────────────────────────────
# Corporativos
# ──────────────────────────────────────────────────────────────
@app.route("/corporativos")
@login_required
def corporativos():
    lista = Corporativo.query.order_by(Corporativo.nombre).all()
    return render_template("corporativos.html", lista=lista)


@app.route("/corporativos/nuevo", methods=["GET", "POST"])
@login_required
def nuevo_corporativo():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("El nombre es obligatorio.", "danger")
            return redirect(url_for("nuevo_corporativo"))
        if Corporativo.query.filter_by(nombre=nombre).first():
            flash("Ya existe un corporativo con ese nombre.", "warning")
            return redirect(url_for("corporativos"))
        c = Corporativo(
            nombre=nombre,
            observaciones=request.form.get("observaciones") or None,
            created_by=current_user.id
        )
        db.session.add(c)
        db.session.commit()
        registrar_actividad("crear_corporativo", "corporativo", c.id)
        flash("Corporativo registrado.", "success")
        return redirect(url_for("corporativos"))
    return render_template("nuevo_corporativo.html")


# ──────────────────────────────────────────────────────────────
# Malas referencias
# ──────────────────────────────────────────────────────────────
@app.route("/malas-referencias")
@login_required
def malas_referencias():
    lista = ReferenciaLaboral.query.filter_by(mala_referencia="Si").order_by(ReferenciaLaboral.fecha.desc()).all()
    return render_template("malas_referencias.html", lista=lista)


@app.route("/malas-referencias/nueva", methods=["GET", "POST"])
@login_required
def nueva_mala_referencia():
    if request.method == "POST":
        postulante_id = request.form.get("postulante_id")
        if not postulante_id:
            flash("Seleccioná un postulante.", "danger")
            return redirect(url_for("nueva_mala_referencia"))
        ref = ReferenciaLaboral(
            postulante_id=int(postulante_id),
            mala_referencia="Si",
            motivo=request.form.get("motivo") or None,
            empresa_relacionada=request.form.get("empresa") or None,
            observaciones=request.form.get("observaciones") or None,
            responsable_id=current_user.id
        )
        db.session.add(ref)
        db.session.commit()
        registrar_actividad("crear_mala_referencia", "referencia", ref.id)
        flash("Referencia registrada. Queda auditoría.", "success")
        return redirect(url_for("malas_referencias"))
    return render_template(
        "nueva_mala_referencia.html",
        postulantes=Postulante.query.order_by(Postulante.nombre_completo).all()
    )


# ──────────────────────────────────────────────────────────────
# Administración
# ──────────────────────────────────────────────────────────────
@app.route("/admin")
@login_required
@admin_required
def admin():
    users = User.query.order_by(User.nombre).all()
    org = Configuracion.query.filter_by(clave="nombre_organizacion").first()
    return render_template(
        "admin.html",
        users=users,
        nombre_org=org.valor if org else "Actus & Asociados S.A."
    )


@app.route("/admin/usuario", methods=["POST"])
@login_required
@admin_required
def crear_usuario():
    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip().lower() or None
    password = request.form.get("password", "")
    rol = request.form.get("rol", "reclutador")

    if not nombre or not password:
        flash("Nombre y contraseña son obligatorios.", "danger")
        return redirect(url_for("admin"))

    if User.query.filter(db.func.lower(User.nombre) == nombre.lower()).first():
        flash("Ya existe un usuario con ese nombre.", "warning")
        return redirect(url_for("admin"))

    u = User(nombre=nombre, email=email, rol=rol)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    registrar_actividad("crear_usuario", "user", u.id)
    flash(f"Usuario {nombre} creado.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/config", methods=["POST"])
@login_required
@admin_required
def guardar_config():
    nombre = request.form.get("nombre_organizacion", "").strip()
    if nombre:
        conf = Configuracion.query.filter_by(clave="nombre_organizacion").first()
        if conf:
            conf.valor = nombre
        else:
            conf = Configuracion(clave="nombre_organizacion", valor=nombre)
            db.session.add(conf)
        db.session.commit()
        flash("Configuración guardada.", "success")
    return redirect(url_for("admin"))


# ──────────────────────────────────────────────────────────────
# API auxiliar (para JS)
# ──────────────────────────────────────────────────────────────
@app.route("/api/interpretar", methods=["POST"])
@login_required
def api_interpretar():
    data = request.get_json() or {}
    texto = data.get("texto", "")
    return jsonify(interpretar_texto(texto))


# ──────────────────────────────────────────────────────────────
# Inicialización de la base de datos
# ──────────────────────────────────────────────────────────────
def init_db():
    with app.app_context():
        os.makedirs(app.instance_path, exist_ok=True)
        db.create_all()

        # Usuario administrador inicial
        if not User.query.filter_by(rol="admin").first():
            admin = User(
                nombre="Administrador",
                email="admin@actus.com.py",
                rol="admin"
            )
            admin.set_password("actus2026")
            db.session.add(admin)

            reclutador = User(
                nombre="María López",
                email="maria@actus.com.py",
                rol="reclutador"
            )
            reclutador.set_password("reclutador123")
            db.session.add(reclutador)

            # Configuración
            conf = Configuracion(clave="nombre_organizacion", valor="Actus & Asociados S.A.")
            db.session.add(conf)

            db.session.commit()
            print("✅ Base de datos inicializada.")
            print("   Admin: nombre=Administrador  /  contraseña=actus2026")
            print("   Reclutador: nombre=María López  /  contraseña=reclutador123")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
