"""Acceso a SQLite, validación y lógica de negocio (compartida por web y API)."""
import re
import sqlite3
from datetime import datetime

from flask import current_app, g

CAMPOS = [
    "nombre", "apellidos", "empresa", "email", "telefono", "estado",
    "direccion", "pais", "comercial", "fecha_alta", "facturacion",
]
OBLIGATORIOS = [c for c in CAMPOS if c != "fecha_alta"]  # fecha_alta se autocompleta
ESTADOS = ["Activo", "Inactivo"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT NOT NULL,
    apellidos           TEXT NOT NULL,
    empresa             TEXT NOT NULL,
    email               TEXT NOT NULL,
    telefono            TEXT NOT NULL,
    estado              TEXT NOT NULL CHECK (estado IN ('Activo', 'Inactivo')),
    direccion           TEXT NOT NULL,
    pais                TEXT NOT NULL,
    comercial           TEXT NOT NULL,
    fecha_alta          TEXT NOT NULL,
    facturacion         REAL NOT NULL CHECK (facturacion >= 0),
    fecha_modificacion  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS historial (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id      INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    fecha           TEXT NOT NULL,
    campo           TEXT NOT NULL,
    valor_anterior  TEXT,
    valor_nuevo     TEXT
);
CREATE INDEX IF NOT EXISTS idx_historial_cliente ON historial(cliente_id);
"""


# ---------- conexión ----------
# Descripcion, parametros y retorno
def get_db():
    """Crea la conexion con la DB (atributo db de g) si esta no existe, g.db.row_factory permite acceder a las columnas por nombre
    y se activan las claves foraneas.
    Retorna g.db.
    g.db existe fuera de esta funcion porque es un atributo del objeto g de la libreria de Flask
    """
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    """Cierra la DB. pop elimina un valor y lo devuelve, este se guarda en db y sirve para cerrar la conexion si db no es vacío
    No devuelve nada
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path):
    #Se crea la DB, cosa que solo pasa en app.py linea 20 cuando no existe la DB
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.commit()
    con.close()


def ahora():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


# ---------- validación ----------
def validar(datos, base=None):
    """Valida y normaliza los datos de un cliente.

    `base` es el cliente existente (dict) en una edición: los campos que no
    vengan en `datos` conservan su valor. Devuelve (limpio, errores).
    """

    # ESTE COMENTARIO ES DEL CLAUDE PERO ESTA FUNCION YA LA HE ENTENDIDO UNA VEZ, MAÑANA LA COMENTO CON CALMA QUE SON LAS 2:30

    limpio, errores = {}, {}
    base = base or {}
    for campo in CAMPOS:
        if campo in datos and datos[campo] is not None:
            valor = datos[campo]
        else:
            valor = base.get(campo, "")
        limpio[campo] = valor.strip() if isinstance(valor, str) else valor

    for campo in OBLIGATORIOS:
        if limpio[campo] in ("", None):
            errores[campo] = "Este campo es obligatorio."

    if "email" not in errores and not EMAIL_RE.match(str(limpio["email"])):
        errores["email"] = "El correo electrónico no tiene un formato válido."

    if "estado" not in errores and limpio["estado"] not in ESTADOS:
        errores["estado"] = "El estado debe ser: " + " o ".join(ESTADOS) + "."

    if "facturacion" not in errores:
        try:
            fact = float(str(limpio["facturacion"]).replace(",", "."))
            if fact != fact or fact in (float("inf"), float("-inf")):
                raise ValueError
            if fact < 0:
                errores["facturacion"] = "La facturación no puede ser negativa."
            else:
                limpio["facturacion"] = round(fact, 2)
        except ValueError:
            errores["facturacion"] = "La facturación debe ser un número."

    if not limpio["fecha_alta"]:
        limpio["fecha_alta"] = datetime.now().strftime("%Y-%m-%d")
    else:
        try:
            datetime.strptime(str(limpio["fecha_alta"]), "%Y-%m-%d")
        except ValueError:
            errores["fecha_alta"] = "La fecha debe tener formato AAAA-MM-DD."

    return limpio, errores


# ---------- consultas ----------
def obtener(cliente_id):
    """Ejecuta en la DB un select del id recibido y coge un resultado (el id es unico asi que solo puede coincidir uno)
    El ? de la consulta es un placeholder que se reemplaza por los valores que le pases despues. Si hay varios ?, se reemplazan
    en el orden en que le pases los parametros, separados por comas.
    Si encuentra un registro lo devuelve y si no devuelve none
    """
    fila = get_db().execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
    return dict(fila) if fila else None


def valores_distintos(columna):
    """De cada columna que le llega a la funcion, se obtienen los valores distintos y se retornan los valores.
    El assert se asegura que a la funcion solo le llegue o "pais" o "comercial".
    """
    assert columna in ("pais", "comercial")  # evita inyección: columna no viene del usuario
    filas = get_db().execute(
        f"SELECT DISTINCT {columna} FROM clientes ORDER BY {columna}").fetchall()
    return [f[0] for f in filas]


def buscar(q="", estado="", pais="", comercial="", pagina=1, por_pagina=10):
    """Llegan la query del buscador y los valores de los desplegables.
    Si hay query, se añade a where esa consulta. Params se multiplica por 3 para cada wildcard de la consulta
    Retorna los resultados como dict y el num. total de resultados
    """
    where, params = [], []
    if q:
        #Si hay query, se añade a where esa consulta. Params se multiplica por 3 para cada wildcard de la consulta
        where.append("(nombre || ' ' || apellidos LIKE ? OR empresa LIKE ? OR email LIKE ?)")
        params += [f"%{q}%"] * 3
    for columna, valor in (("estado", estado), ("pais", pais), ("comercial", comercial)):
        #Para cada columna, si tiene valor, se sustituyen los wildcards con sus valores en orden. Se añaden a params para mas tarde
        if valor:
            where.append(f"{columna} = ?")
            params.append(valor)
    sql_where = ("WHERE " + " AND ".join(where)) if where else ""

    
    db = get_db()

    total = db.execute(f"SELECT COUNT(*) FROM clientes {sql_where}", params).fetchone()[0]
    
    """Si habia q, llegara a esta consulta WHERE nombre LIKE q OR apellidos LIKE q OR email LIKE q AND (los filtros de los desplegables)
    Si no habia q, llegará WHERE estado, pais y comercial = valor (si habia valor), separados con ands.
    """
    filas = db.execute(
        f"SELECT * FROM clientes {sql_where} ORDER BY id LIMIT ? OFFSET ?",
        params + [por_pagina, (pagina - 1) * por_pagina],
    ).fetchall()
    return [dict(f) for f in filas], total


# ---------- escritura ----------
def crear(limpio):
    db = get_db()
    cur = db.execute(
        f"INSERT INTO clientes ({', '.join(CAMPOS)}, fecha_modificacion) "
        f"VALUES ({', '.join('?' * len(CAMPOS))}, ?)",
        [limpio[c] for c in CAMPOS] + [ahora()],
    )
    db.commit()
    return cur.lastrowid


def actualizar(cliente_id, limpio, anterior):
    """Actualiza el cliente y registra en `historial` cada campo que cambió.

    Todo ocurre en una única transacción: o se guarda cliente + histórico, o nada.
    """
    db = get_db()
    momento = ahora()
    cambios = [(c, anterior[c], limpio[c]) for c in CAMPOS if str(anterior[c]) != str(limpio[c])]
    if not cambios:
        return []
    try:
        db.execute(
            f"UPDATE clientes SET {', '.join(c + ' = ?' for c in CAMPOS)}, "
            f"fecha_modificacion = ? WHERE id = ?",
            [limpio[c] for c in CAMPOS] + [momento, cliente_id],
        )
        db.executemany(
            "INSERT INTO historial (cliente_id, fecha, campo, valor_anterior, valor_nuevo) "
            "VALUES (?, ?, ?, ?, ?)",
            [(cliente_id, momento, c, str(a), str(n)) for c, a, n in cambios],
        )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise
    return cambios


def eliminar(cliente_id):
    db = get_db()
    cur = db.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
    db.commit()
    return cur.rowcount > 0


def historial(cliente_id):
    filas = get_db().execute(
        "SELECT * FROM historial WHERE cliente_id = ? ORDER BY id DESC", (cliente_id,)
    ).fetchall()
    return [dict(f) for f in filas]
