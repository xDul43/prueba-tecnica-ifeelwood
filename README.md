# Gestión de clientes (Flask + SQLite)

Aplicación web CRUD con API REST e histórico de cambios.

## Puesta en marcha

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py        # crea clientes.db con 60 clientes ficticios (ya incluida; esto la regenera)
python app.py         # http://127.0.0.1:5000
python tests/test_app.py   # pruebas automáticas (usan una copia temporal de la BD)
```

## Estructura

```
app.py         Rutas: web (HTML) y API REST. Solo orquesta; no contiene SQL.
db.py          Esquema, conexión, validación, consultas y escritura + histórico.
seed.py        Genera los datos ficticios (semilla fija → reproducible).
templates/     Jinja2: base, lista, detalle (con histórico), formulario, 404.
static/        CSS (claro/oscuro automático).
tests/         Pruebas end-to-end con el cliente de test de Flask.
```

## Decisiones técnicas

- **Flask**: para una app pequeña con vistas HTML y cuatro endpoints JSON es lo más
  directo: poca magia, fácil de leer y de modificar en una entrevista. FastAPI sería mejor
  si fuera solo API; Django aportaría ORM y admin pero con mucho más andamiaje del necesario.
- **`sqlite3` de la librería estándar, sin ORM**: el SQL es corto, legible y todo está
  parametrizado (sin inyección SQL). Los nombres de columna dinámicos salen de una lista
  fija en el código, nunca del usuario.
- **Una sola validación** (`db.validar`) para web y API: mismas reglas, mismos mensajes.
- **Histórico transaccional**: cliente + filas de `historial` se guardan en la misma
  transacción; solo se registran los campos que realmente cambian (una fila por campo).
  Al eliminar un cliente se elimina su histórico (`ON DELETE CASCADE`).
- **Eliminar**: es un `POST` (nunca un `GET`) con `confirm()` en el navegador.
- **Filtros y paginación en SQL** (`LIMIT/OFFSET`), y los filtros se conservan al paginar.
- **Los formularios con error** se vuelven a mostrar con los datos escritos y el mensaje bajo cada campo.

## Validaciones

Campos obligatorios · email con formato válido · estado ∈ {Activo, Inactivo} ·
facturación numérica ≥ 0 (acepta `1234,56` y `1234.56`) · fecha de alta `AAAA-MM-DD`
(si se omite, hoy) · IDs inexistentes → página 404 / JSON 404.

## API REST

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/clientes` | Listado. Query: `q`, `estado`, `pais`, `comercial`, `pagina`, `por_pagina` (máx. 100) |
| GET | `/api/clientes/{id}` | Un cliente (404 si no existe) |
| POST | `/api/clientes` | Crear (201 + cabecera `Location`; 422 si hay errores) |
| PUT | `/api/clientes/{id}` | Actualizar. Los campos ausentes conservan su valor |
| GET | `/api/clientes/{id}/historial` | Extra: histórico de cambios |

```bash
curl -X POST localhost:5000/api/clientes -H "Content-Type: application/json" -d '{
  "nombre":"Ana","apellidos":"Ruiz Gil","empresa":"Acme S.L.","email":"ana@acme.es",
  "telefono":"+34 600 111 222","estado":"Activo","direccion":"Calle Sol 1, Madrid",
  "pais":"España","comercial":"Ana Torres","facturacion":1500.50}'

curl -X PUT localhost:5000/api/clientes/61 -H "Content-Type: application/json" -d '{"estado":"Inactivo"}'
```

## Limitaciones conocidas (mejoras posibles)

- Sin autenticación ni protección CSRF (fuera del alcance de la prueba; añadir Flask-WTF/CSRF en producción).
- Sin ordenación por columnas; sin tests unitarios finos de `validar`.
- `debug=True` solo para desarrollo; en producción usar gunicorn/waitress y una `SECRET_KEY` real.
