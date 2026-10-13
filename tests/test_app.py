import os, sys, tempfile, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from app import create_app
import db

tmp = tempfile.mkdtemp(); ruta = os.path.join(tmp, "t.db")
shutil.copy(os.path.join(ROOT, "clientes.db"), ruta)
app = create_app(ruta); c = app.test_client()

assert c.get("/").status_code == 200
r = c.get("/?q=garcia&estado=Activo&pais=España"); assert r.status_code == 200
assert c.get("/?pagina=999").status_code == 302          # página fuera de rango
assert c.get("/clientes/9999").status_code == 404
assert c.get("/clientes/9999/editar").status_code == 404
assert c.post("/clientes/9999/eliminar").status_code == 302
assert c.get("/clientes/1").status_code == 200
assert c.get("/clientes/nuevo").status_code == 200

# Web: validación
r = c.post("/clientes/nuevo", data={"nombre": "", "email": "mal", "facturacion": "-5"})
assert r.status_code == 400 and "formato válido" in r.get_data(as_text=True)

# Web: crear / editar / histórico / eliminar
datos = dict(nombre="Test", apellidos="Uno", empresa="X SL", email="t@x.com", telefono="123",
             estado="Activo", direccion="Calle 1", pais="España", comercial="Ana Torres", facturacion="10,5")
r = c.post("/clientes/nuevo", data=datos); assert r.status_code == 302
nid = int(r.headers["Location"].rsplit("/", 1)[1])
datos.update(empresa="Y SL", facturacion="99")
assert c.post(f"/clientes/{nid}/editar", data=datos).status_code == 302
page = c.get(f"/clientes/{nid}").get_data(as_text=True)
assert "X SL" in page and "Y SL" in page
assert c.post(f"/clientes/{nid}/eliminar").status_code == 302
assert c.get(f"/clientes/{nid}").status_code == 404

# API
j = c.get("/api/clientes?por_pagina=5").get_json(); assert j["total"] == 60 and len(j["clientes"]) == 5
assert c.get("/api/clientes/1").get_json()["id"] == 1
assert c.get("/api/clientes/9999").status_code == 404
r = c.post("/api/clientes", json={"nombre": "A"}); assert r.status_code == 422 and "email" in r.get_json()["detalles"]
assert c.post("/api/clientes", data="no json", content_type="text/plain").status_code == 400
r = c.post("/api/clientes", json={**datos, "facturacion": 5}); assert r.status_code == 201
nid = r.get_json()["id"]
r = c.put(f"/api/clientes/{nid}", json={"estado": "Inactivo", "facturacion": 7}); assert r.status_code == 200
assert c.put(f"/api/clientes/{nid}", json={"facturacion": -1}).status_code == 422
assert c.put("/api/clientes/9999", json={}).status_code == 404
h = c.get(f"/api/clientes/{nid}/historial").get_json()
assert {x["campo"] for x in h} == {"estado", "facturacion"}, h
print("TODO OK")
shutil.rmtree(tmp)
