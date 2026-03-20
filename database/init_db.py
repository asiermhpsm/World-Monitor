"""
Inicialización de la base de datos.
Ejecuta este script una sola vez para crear todas las tablas.

Uso:
    python database/init_db.py
"""

import sys
from pathlib import Path

# Permite importar config.py desde la raíz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.database import Base, engine
from config import DB_PATH


def init_db():
    print(f"Inicializando base de datos en: {DB_PATH}")
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas:")
    for table_name in Base.metadata.tables:
        print(f"  ✓ {table_name}")
    print("Base de datos lista.")


if __name__ == "__main__":
    init_db()
