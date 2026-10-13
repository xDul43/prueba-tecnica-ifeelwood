"""Crea clientes.db y la rellena con 60 clientes ficticios.  Uso: python seed.py"""
import os
import random
import sqlite3
from datetime import date, datetime, timedelta

import db

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clientes.db")
random.seed(42)  # datos reproducibles

NOMBRES = ["Lucía", "Carlos", "Marta", "Javier", "Elena", "Pablo", "Sofía", "Andrés", "Laura",
           "Miguel", "Carmen", "David", "Paula", "Sergio", "Irene", "Álvaro", "Nuria", "Hugo"]
APELLIDOS = ["García", "Martínez", "López", "Sánchez", "Pérez", "Gómez", "Ruiz", "Hernández",
             "Díaz", "Moreno", "Muñoz", "Álvarez", "Romero", "Navarro", "Torres", "Vidal"]
EMPRESAS = ["Soluciones", "Grupo", "Industrias", "Logística", "Consultoría", "Talleres",
            "Distribuciones", "Servicios", "Tecnologías", "Construcciones"]
SECTORES = ["Mediterráneo", "Ibérica", "Norte", "Atlántico", "Delta", "Horizonte", "Cantábrico",
            "Levante", "Pirineos", "Central"]
SUFIJOS = ["S.L.", "S.A.", "S.L.U."]
# país: (prefijo teléfono, ciudades)
PAISES = {
    "España": ("+34", ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao"]),
    "Portugal": ("+351", ["Lisboa", "Oporto", "Braga"]),
    "Francia": ("+33", ["París", "Lyon", "Marsella"]),
    "Italia": ("+39", ["Roma", "Milán", "Turín"]),
    "Alemania": ("+49", ["Berlín", "Múnich", "Hamburgo"]),
}
CALLES = ["Calle Mayor", "Avenida de la Constitución", "Calle del Sol", "Paseo del Prado",
          "Calle Real", "Avenida del Puerto", "Calle Nueva"]
COMERCIALES = ["Ana Torres", "Raúl Ortega", "Beatriz Campos", "Íñigo Salas", "Marina Vega"]


def quitar_tildes(s):
    return s.translate(str.maketrans("áéíóúñÁÉÍÓÚÑ", "aeiounAEIOUN"))


def generar(n=60):
    for _ in range(n):
        nombre, apellidos = random.choice(NOMBRES), f"{random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"
        sector = random.choice(SECTORES)
        empresa = f"{random.choice(EMPRESAS)} {sector} {random.choice(SUFIJOS)}"
        pais = random.choices(list(PAISES), weights=[5, 2, 2, 2, 2])[0]
        prefijo, ciudades = PAISES[pais]
        dominio = quitar_tildes(sector).lower() + random.choice([".com", ".es", ".eu"])
        email = f"{quitar_tildes(nombre).lower()}.{quitar_tildes(apellidos.split()[0]).lower()}@{dominio}"
        alta = date.today() - timedelta(days=random.randint(30, 1500))
        yield {
            "nombre": nombre, "apellidos": apellidos, "empresa": empresa, "email": email,
            "telefono": f"{prefijo} {random.randint(600, 799)} {random.randint(100, 999)} {random.randint(100, 999)}",
            "estado": random.choices(["Activo", "Inactivo"], weights=[4, 1])[0],
            "direccion": f"{random.choice(CALLES)} {random.randint(1, 120)}, {random.choice(ciudades)}",
            "pais": pais, "comercial": random.choice(COMERCIALES),
            "fecha_alta": alta.isoformat(), "facturacion": round(random.uniform(0, 250000), 2),
        }


if __name__ == "__main__":
    if os.path.exists(RUTA):
        os.remove(RUTA)
    db.init_db(RUTA)
    con = sqlite3.connect(RUTA)
    ahora = datetime.now().isoformat(sep=" ", timespec="seconds")
    cols = db.CAMPOS
    con.executemany(
        f"INSERT INTO clientes ({', '.join(cols)}, fecha_modificacion) VALUES ({', '.join('?' * len(cols))}, ?)",
        [[c[k] for k in cols] + [ahora] for c in generar()])
    con.commit()
    print("Base de datos creada con", con.execute("SELECT COUNT(*) FROM clientes").fetchone()[0], "clientes.")
    con.close()
