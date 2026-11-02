from database.queries import PRODUCT_LIST


class ProductoModel:
    def __init__(self, db):
        self.db = db

    def list_all(self, search="", filter_name="Todos"):
        params = (search,) * 7 + (filter_name,) * 6

        with self.db.cursor() as (_, cursor):
            cursor.execute(PRODUCT_LIST, params)
            return cursor.fetchall()

    def get(self, pid):
        sql = """
            SELECT
                p.*,
                pa.nombre AS principio_activo,
                m.nombre AS marca,
                c.nombre AS categoria
            FROM productos p
            LEFT JOIN principios_activos pa
                ON pa.id = p.principio_activo_id
            LEFT JOIN marcas m
                ON m.id = p.marca_id
            LEFT JOIN categorias c
                ON c.id = p.categoria_id
            WHERE p.id = %s
        """

        with self.db.cursor() as (_, cursor):
            cursor.execute(sql, (pid,))
            return cursor.fetchone()

    def _check_duplicate(self, data, exclude_id=None):
        """Evita registrar dos veces el mismo producto vendible.

        Identidad: principio activo + marca + concentración + unidad + forma
        farmacéutica + presentación + cantidad por presentación.
        """
        (_, _, _, active_id, brand_id, conc, unit, form, _, presentation,
         present_qty, present_unit, *_rest) = data
        sql = """
            SELECT id, codigo FROM productos
            WHERE principio_activo_id = %s
              AND marca_id <=> %s
              AND concentracion <=> %s
              AND unidad_concentracion <=> %s
              AND forma_farmaceutica <=> %s
              AND presentacion <=> %s
              AND cantidad_presentacion = %s
              AND unidad_presentacion = %s
              AND (%s IS NULL OR id <> %s)
            LIMIT 1
        """
        with self.db.cursor() as (_, cursor):
            cursor.execute(sql, (active_id, brand_id, conc, unit, form, presentation,
                                 present_qty, present_unit, exclude_id, exclude_id))
            duplicate = cursor.fetchone()
        if duplicate:
            raise ValueError(
                f"Ya existe un producto con las mismas características (código {duplicate['codigo']}). "
                "Cambie la concentración, forma, presentación o marca si es un producto distinto."
            )

    def create(self, data):
        self._check_duplicate(data)
        sql = """
            INSERT INTO productos (
                codigo,
                codigo_barras,
                nombre_comercial,
                principio_activo_id,
                marca_id,
                concentracion,
                unidad_concentracion,
                forma_farmaceutica,
                via_administracion,
                presentacion,
                cantidad_presentacion,
                unidad_presentacion,
                descripcion,
                categoria_id,
                precio_venta,
                stock_minimo,
                requiere_receta,
                control_especial,
                estado
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """

        with self.db.cursor() as (connection, cursor):
            cursor.execute(sql, data)
            connection.commit()
            return cursor.lastrowid

    def update(self, pid, data):
        self._check_duplicate(data, exclude_id=pid)
        sql = """
            UPDATE productos
            SET
                codigo = %s,
                codigo_barras = %s,
                nombre_comercial = %s,
                principio_activo_id = %s,
                marca_id = %s,
                concentracion = %s,
                unidad_concentracion = %s,
                forma_farmaceutica = %s,
                via_administracion = %s,
                presentacion = %s,
                cantidad_presentacion = %s,
                unidad_presentacion = %s,
                descripcion = %s,
                categoria_id = %s,
                precio_venta = %s,
                stock_minimo = %s,
                requiere_receta = %s,
                control_especial = %s,
                estado = %s
            WHERE id = %s
        """

        with self.db.cursor() as (connection, cursor):
            cursor.execute(sql, (*data, pid))
            connection.commit()

    def get_or_create_active(self, name):
        name = (name or "").strip()

        if not name:
            return None

        with self.db.cursor() as (connection, cursor):
            cursor.execute(
                """
                SELECT id
                FROM principios_activos
                WHERE LOWER(nombre) = LOWER(%s)
                LIMIT 1
                """,
                (name,),
            )

            row = cursor.fetchone()

            if row:
                return row["id"]

            cursor.execute(
                "INSERT INTO principios_activos(nombre) VALUES(%s)",
                (name,),
            )
            connection.commit()

            return cursor.lastrowid

    def get_or_create_brand(self, name):
        name = (name or "").strip()

        if not name or name.lower() in ("sin marca", "sin laboratorio"):
            return None

        with self.db.cursor() as (connection, cursor):
            cursor.execute(
                """
                SELECT id
                FROM marcas
                WHERE LOWER(nombre) = LOWER(%s)
                LIMIT 1
                """,
                (name,),
            )

            row = cursor.fetchone()

            if row:
                return row["id"]

            cursor.execute(
                "INSERT INTO marcas(nombre, laboratorio) VALUES(%s, %s)",
                (name, name),
            )
            connection.commit()

            return cursor.lastrowid

    def catalog_options(self):
        with self.db.cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, nombre
                FROM principios_activos
                WHERE estado = 'Activo'
                ORDER BY nombre
                """
            )
            active_ingredients = cursor.fetchall()

            cursor.execute(
                """
                SELECT id, nombre
                FROM marcas
                WHERE estado = 'Activo'
                ORDER BY nombre
                """
            )
            brands = cursor.fetchall()

            cursor.execute(
                """
                SELECT id, nombre
                FROM categorias
                WHERE estado = 'Activo'
                ORDER BY nombre
                """
            )
            categories = cursor.fetchall()

        return active_ingredients, brands, categories

    def alternatives(self, pid):
        with self.db.cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT nombre
                FROM nombres_alternativos
                WHERE producto_id = %s
                ORDER BY nombre
                """,
                (pid,),
            )

            return [row["nombre"] for row in cursor.fetchall()]

    def lots(self, pid):
        sql = """
            SELECT
                l.id,
                l.numero_lote,
                l.fecha_fabricacion,
                l.fecha_vencimiento,
                l.cantidad_inicial,
                l.cantidad_actual,
                l.precio_compra,
                l.fecha_recepcion,
                l.estado,
                l.ubicacion,
                COALESCE(pr.nombre, 'Sin proveedor') AS proveedor
            FROM lotes l
            LEFT JOIN proveedores pr
                ON pr.id = l.proveedor_id
            WHERE l.producto_id = %s
            ORDER BY
                l.fecha_vencimiento ASC,
                l.id ASC
        """

        with self.db.cursor() as (_, cursor):
            cursor.execute(sql, (pid,))
            return cursor.fetchall()

    def save_alternatives(self, pid, names):
        with self.db.cursor() as (connection, cursor):
            cursor.execute(
                """
                DELETE FROM nombres_alternativos
                WHERE producto_id = %s
                """,
                (pid,),
            )

            for name in names:
                clean_name = name.strip()

                if clean_name:
                    cursor.execute(
                        """
                        INSERT INTO nombres_alternativos(producto_id, nombre)
                        VALUES(%s, %s)
                        """,
                        (pid, clean_name),
                    )

            connection.commit()
