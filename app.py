"""Aplicación web + API REST de gestión de clientes (Flask + SQLite)."""
import os
import sqlite3

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)

import db

POR_PAGINA = 10
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app(database=None):
    app = Flask(__name__)
    app.config["DATABASE"] = database or os.path.join(BASE_DIR, "clientes.db")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-solo-para-la-prueba")
    app.teardown_appcontext(db.close_db)
    if not os.path.exists(app.config["DATABASE"]):
        db.init_db(app.config["DATABASE"])

    # ===================== WEB =====================
    @app.route("/")
    def lista():
        filtros = {k: request.args.get(k, "").strip() for k in ("q", "estado", "pais", "comercial")}
        pagina = max(request.args.get("pagina", 1, type=int), 1)
        clientes, total = db.buscar(**filtros, pagina=pagina, por_pagina=POR_PAGINA)
        paginas = max((total + POR_PAGINA - 1) // POR_PAGINA, 1)
        if pagina > paginas:
            # Esto sucede cuando filtras desde un num. de pagina mas grande que el num. de paginas que restan al aplicar el filtro
            return redirect(url_for("lista", **filtros, pagina=paginas))
        return render_template(
            "lista.html", clientes=clientes, total=total, pagina=pagina, paginas=paginas,
            filtros=filtros, estados=db.ESTADOS,
            paises=db.valores_distintos("pais"), comerciales=db.valores_distintos("comercial"))

    @app.route("/clientes/<int:cliente_id>")
    def detalle(cliente_id):
        cliente = db.obtener(cliente_id) or abort(404)
        return render_template("detalle.html", c=cliente, historial=db.historial(cliente_id))

    @app.route("/clientes/nuevo", methods=["GET", "POST"])
    def nuevo():
        if request.method == "POST":
            limpio, errores = db.validar(request.form)
            if not errores:
                try:
                    nuevo_id = db.crear(limpio)
                except sqlite3.Error:
                    flash("No se pudo guardar el cliente por un error de base de datos.", "error")
                else:
                    flash("Cliente creado correctamente.", "ok")
                    return redirect(url_for("detalle", cliente_id=nuevo_id))
            else:
                flash("Revisa los campos marcados en rojo.", "error")
            return render_template("form.html", c=limpio, errores=errores,
                                   estados=db.ESTADOS, editar=False), 400
        return render_template("form.html", c={"estado": "Activo", "facturacion": 0},
                               errores={}, estados=db.ESTADOS, editar=False)

    @app.route("/clientes/<int:cliente_id>/editar", methods=["GET", "POST"])
    def editar(cliente_id):
        actual = db.obtener(cliente_id) or abort(404)
        if request.method == "POST":
            limpio, errores = db.validar(request.form, base=actual)
            if not errores:
                try:
                    cambios = db.actualizar(cliente_id, limpio, actual)
                except sqlite3.Error:
                    flash("No se pudo guardar por un error de base de datos.", "error")
                else:
                    flash(f"Cliente actualizado ({len(cambios)} campo(s) modificado(s))."
                          if cambios else "No había cambios que guardar.", "ok")
                    return redirect(url_for("detalle", cliente_id=cliente_id))
            else:
                flash("Revisa los campos marcados en rojo.", "error")
            limpio["id"] = cliente_id
            return render_template("form.html", c=limpio, errores=errores,
                                   estados=db.ESTADOS, editar=True), 400
        return render_template("form.html", c=actual, errores={}, estados=db.ESTADOS, editar=True)

    @app.post("/clientes/<int:cliente_id>/eliminar")
    def eliminar(cliente_id):
        if db.eliminar(cliente_id):
            flash("Cliente eliminado.", "ok")
        else:
            flash("El cliente que intentas eliminar ya no existe.", "error")
        return redirect(url_for("lista"))

    @app.errorhandler(404)
    def no_encontrado(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Recurso no encontrado"), 404
        return render_template("404.html"), 404

    # ===================== API REST =====================
    def cliente_json(c):
        return c  # las columnas ya son serializables

    @app.get("/api/clientes")
    def api_lista():
        pagina = max(request.args.get("pagina", 1, type=int), 1)
        por_pagina = min(max(request.args.get("por_pagina", 20, type=int), 1), 100)
        clientes, total = db.buscar(
            q=request.args.get("q", ""), estado=request.args.get("estado", ""),
            pais=request.args.get("pais", ""), comercial=request.args.get("comercial", ""),
            pagina=pagina, por_pagina=por_pagina)
        return jsonify(total=total, pagina=pagina, por_pagina=por_pagina,
                       clientes=[cliente_json(c) for c in clientes])

    @app.get("/api/clientes/<int:cliente_id>")
    def api_detalle(cliente_id):
        cliente = db.obtener(cliente_id)
        if not cliente:
            return jsonify(error=f"No existe el cliente {cliente_id}"), 404
        return jsonify(cliente_json(cliente))

    @app.post("/api/clientes")
    def api_crear():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error="El cuerpo debe ser un objeto JSON"), 400
        limpio, errores = db.validar(datos)
        if errores:
            return jsonify(error="Datos no válidos", detalles=errores), 422
        nuevo_id = db.crear(limpio)
        resp = jsonify(cliente_json(db.obtener(nuevo_id)))
        resp.status_code = 201
        resp.headers["Location"] = url_for("api_detalle", cliente_id=nuevo_id)
        return resp

    @app.put("/api/clientes/<int:cliente_id>")
    def api_actualizar(cliente_id):
        actual = db.obtener(cliente_id)
        if not actual:
            return jsonify(error=f"No existe el cliente {cliente_id}"), 404
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify(error="El cuerpo debe ser un objeto JSON"), 400
        limpio, errores = db.validar(datos, base=actual)
        if errores:
            return jsonify(error="Datos no válidos", detalles=errores), 422
        db.actualizar(cliente_id, limpio, actual)
        return jsonify(cliente_json(db.obtener(cliente_id)))

    # Extra (no exigido): histórico por API
    @app.get("/api/clientes/<int:cliente_id>/historial")
    def api_historial(cliente_id):
        if not db.obtener(cliente_id):
            return jsonify(error=f"No existe el cliente {cliente_id}"), 404
        return jsonify(db.historial(cliente_id))

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
