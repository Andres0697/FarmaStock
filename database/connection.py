import os
from contextlib import contextmanager

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


class Database:
    """Acceso a MySQL: conexiones, consultas simples y transacciones."""

    def __init__(self):
        self.config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "database": os.getenv("DB_NAME", "farmastock"),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
        }

    def get_connection(self):
        return mysql.connector.connect(**self.config)

    def test_connection(self):
        connection = self.get_connection()
        connection.close()

    @contextmanager
    def cursor(self, dictionary=True):
        """Conexión para consultas simples.

        Quien escribe datos debe llamar a connection.commit(). Si ocurre un
        error, se hace rollback automático antes de cerrar la conexión.
        """
        connection = None
        cursor = None
        try:
            connection = self.get_connection()
            cursor = connection.cursor(dictionary=dictionary)
            yield connection, cursor
        except Exception:
            if connection:
                connection.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    @contextmanager
    def transaction(self, dictionary=True):
        """Transacción atómica: todo se guarda o nada se guarda.

        Uso:
            with db.transaction() as cursor:
                cursor.execute(...)
                cursor.execute(...)

        Si el bloque termina sin errores se hace commit. Si lanza cualquier
        excepción se hace rollback y la excepción se vuelve a lanzar.
        """
        connection = self.get_connection()
        cursor = connection.cursor(dictionary=dictionary)
        try:
            connection.start_transaction()
            yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
