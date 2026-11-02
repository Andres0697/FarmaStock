# FarmaStock

<p align="center"><img src="assets/logo.png" width="120" alt="Logo FarmaStock"></p>

Sistema de escritorio para gestión académica de inventario y ventas de farmacia.

## Tecnologías

- Python 3
- PySide6
- MySQL
- mysql-connector-python
- python-dotenv
- QSS

## Funcionalidades principales

- Inicio de sesión con roles Administrador y Vendedor.
- Catálogo farmacéutico estructurado.
- Principio activo, marca, concentración, unidad, forma farmacéutica y presentación.
- Nombres alternativos para facilitar la búsqueda.
- Productos con código interno y código de barras opcional.
- Inventario separado por lotes.
- Fecha de vencimiento por lote.
- Proveedor y precio de compra por lote.
- FEFO en las ventas.
- Bloqueo de venta de lotes vencidos o no disponibles.
- Entradas de inventario.
- Movimientos de inventario.
- Dashboard con stock, vencimientos y ventas.
- Alertas de stock bajo y próximos vencimientos.
- Historial de ventas y detalle por lote.
- Categorías, proveedores y usuarios.
- Validaciones y mensajes en español.
- Interfaz compacta con pestañas y paneles para evitar formularios gigantes.

## Instalación

1. Instala Python 3.
2. Instala dependencias:

```bash
pip install -r requirements.txt
```

3. Crea `.env` tomando como base `.env.example` y coloca la contraseña local de MySQL.
4. En MySQL ejecuta `sql/instalacion_completa.sql` para crear la base de datos y cargar los datos de demostración en una sola ejecución. También se incluyen `database.sql` y `seed.sql` por separado.
5. Inicia:

```bash
python main.py
```

### Credenciales de demostración

- Administrador: `admin` / `admin123`
- Vendedor: `vendedor` / `vendedor123`

## Importante sobre la base de datos

`sql/database.sql` y `sql/instalacion_completa.sql` recrean la base de datos `farmastock` desde cero para garantizar que la estructura nueva quede completa. Esto elimina la base de datos anterior, por lo que debe utilizarse como instalación inicial o después de respaldar información que se quiera conservar.

## Lógica de inventario

El producto describe qué se vende. El lote representa una existencia concreta del producto y contiene su número de lote, vencimiento, cantidad, proveedor, precio de compra y ubicación.

Las ventas aplican FEFO (First Expiry, First Out): primero se consume el lote válido que vence antes. Si una venta necesita más unidades de las que tiene el primer lote, continúa con el siguiente lote válido.

## Nota académica

Los productos del `seed.sql` son datos ficticios de demostración para probar la aplicación. El sistema no sustituye los procedimientos ni requisitos regulatorios específicos de una farmacia real.

## Código de barras
El campo `Código de barras (EAN/UPC)` es opcional. Si el medicamento ya tiene un código de barras impreso en su caja o envase, escribe ese número (normalmente 8 a 14 dígitos; en muchos productos se usa EAN-13). Si el producto no tiene código de barras, déjalo vacío y utiliza el código interno de FarmaStock, por ejemplo `FAR-021`.

Los códigos de ejemplo incluidos en `instalacion_completa.sql` son datos demostrativos del proyecto y no deben interpretarse como códigos comerciales reales.

## Marca / laboratorio y principio activo
En Nuevo/Editar producto se pueden seleccionar valores existentes o escribir una marca/laboratorio y un principio activo nuevos. Si no existen, FarmaStock los registra automáticamente en el catálogo.

## Lotes desde Productos
El botón `Ver lotes` ya no es solamente informativo. Desde esa ventana se pueden consultar los lotes del producto, registrar una nueva entrada y ajustar el lote seleccionado.

### Corrección de lotes v2
Si ya habías creado la base de datos con una versión anterior y en **Productos > Ver lotes** no aparecen registros, ejecuta `sql/actualizar_lotes_v2.sql` sobre la base `farmastock`. En una instalación nueva usa `sql/instalacion_completa.sql`.


---

## Versión ampliada (migraciones 001–006)

Al iniciar, `main.py` aplica automáticamente (si falla, muestra el error y no abre la aplicación) las migraciones pendientes de `sql/migraciones/`
(tabla de control `schema_migraciones`). Cada migración tiene su script `_down.sql` para revertirla:

```bash
python -m database.migrations            # aplicar pendientes
python -m database.migrations rollback   # revertir la última
```

| Migración | Agrega |
|---|---|
| 001 | Rol **Regente**, `bitacora_auditoria`, `desviaciones_fefo`, usuario `regente` / `regente123` |
| 002 | `registro_sanitario`, `categoria_dispensacion`, `historial_precios` |
| 003 | `libro_controlados` |
| 004 | `ordenes_compra`, `detalle_orden_compra`, `cuentas_por_pagar`, `pagos_proveedor` |
| 005 | `clientes`, `turnos_caja`, `abonos_cliente`, `notas_credito` y columnas de pago en `ventas` |
| 006 | `ajustes_inventario` |
| 007 | **Correctiva**: `ventas.monto_recibido`, `ventas.fecha_anulacion`, `desviaciones_fefo.producto_id`, tabla `recetas_venta` |
| 008 | `entradas_inventario` y `entrada_detalle` (entradas de mercadería por factura) |
| 009 | `pagos_venta` (pagos por venta; permite pago combinado y reportes por método) |
| 010 | `recepciones_compra` y `recepcion_detalle` (recepciones parciales de compras, estado «Parcial») |

Las migraciones 007–010 son idempotentes (se pueden repetir tras un fallo) y no modifican datos existentes.
Los antiguos `001_ventas_pago_anulacion_desviaciones` y `002_entradas_mercaderia` compartían número con otras migraciones,
por lo que nunca se aplicaban; se movieron a `sql/migraciones/obsoletas/` y su contenido pasó a la 007 y 008.
Cada versión debe ser única: el ejecutor lanza un error si encuentra números repetidos.

### Conciliación del Kardex
La existencia de cada lote debe coincidir con la suma de sus movimientos. Para revisarlo (solo lectura):

```bash
python -m database.reconciliacion
```

Si hay diferencias, revise el stock físico y, solo entonces, agregue los movimientos de ajuste con
`python -m database.reconciliacion --aplicar --usuario-id 1 --motivo "Conciliación inicial"`. No modifica `lotes`.

### Pruebas
```bash
python -m unittest discover -s tests -t .          # pruebas sin base de datos
docker compose -f tests/docker-compose.yml up -d   # MySQL desechable (puerto 3307)
$env:FARMASTOCK_TEST_DB="1"                        # PowerShell; en Linux/macOS: export FARMASTOCK_TEST_DB=1
python -m unittest tests.test_integracion_mysql -v # pruebas con MySQL real (base farmastock_test)
```

### Qué incluye
- **Venta con lote real**: campo *Lote real* (escanear/escribir). Sugerencia FEFO, advertencia si hay un lote que vence antes, registro de la desviación con motivo, bloqueo de lotes vencidos/inexistentes/sin stock. Venta por unidad o caja/blíster.
- **Controlados / receta retenida**: se piden paciente, médico y número de receta; alimentan el libro de controlados.
- **Caja**: apertura/cierre de turno con arqueo; es obligatorio tener turno abierto para vender. Pagos: efectivo, tarjeta, transferencia y crédito. Recibo en PDF con espacio para RUC y autorización DGI.
- **Devoluciones y anulaciones** con nota de crédito; reintegran al lote exacto.
- **Compras**: órdenes, recepción (genera lotes), cuentas por pagar, reabastecimiento sugerido por rotación.
- **Ajustes**: merma, vencido, devolución a proveedor y conteo físico por lote.
- **Roles**: Administrador, Regente y Vendedor (`utils/permisos.py`). El vendedor no ajusta inventario, no cambia precios ni anula ventas.
- **Auditoría**, **clientes y crédito**, **historial de precios**, **sustitutos** por principio activo, **reportes** exportables a Excel/PDF y **respaldos** automáticos (requiere `mysqldump` en el PATH; se guardan en `backups/`).

### Credenciales de demostración
`admin / admin123` · `regente / regente123` · `vendedor / vendedor123`

### Notas
- El **nombre genérico** corresponde al *principio activo* ya existente; el **nombre comercial** a `nombre_comercial`.
- Instalación nueva: ejecutar `sql/instalacion_completa.sql` y luego iniciar la app (aplica 001–006).
- Los datos fiscales del recibo son un espacio a completar; no sustituyen requisitos reales de la DGI.


---

## Etapa 3: inventario y lotes (cambios)

- **Una sola vía para cambiar existencias:** se eliminó el ajuste libre «+/-». Los cambios de cantidad se hacen con
  *Ajustar: merma / conteo / devolución* (`AjusteModel`), que exige permiso, motivo (mínimo 5 letras), deja el movimiento,
  el registro en `ajustes_inventario` y la bitácora. El conteo físico sirve para corregir hacia arriba o hacia abajo.
- **Alta de lote validada** (`InventarioModel.create_lot`): permiso `ajustar_inventario`, lote no vencido, fechas coherentes,
  producto y proveedor activos, y un lote ya existente no se suma por esta vía (use *Entradas de mercadería* con la factura).
- **Cuarentena de lotes:** botón *Bloquear / liberar lote* en *Productos > Ver lotes*. Un lote en cuarentena no se vende ni cuenta
  como disponible, conserva su cantidad física y ajustar su cantidad no lo libera. Queda en la bitácora con el motivo.
- **Kardex con saldo por lote** en *Inventario > Movimientos* (requiere MySQL 8 por la función de ventana).
- **Permisos coherentes:** anular ventas y registrar entradas de mercadería aceptan Administrador y Regente (la interfaz y la base usan la misma regla).
- **Sustitutos:** solo se marcan «Equivalente» si coinciden principio activo, concentración, unidad, forma y vía; si no, «Verificar».
- **Productos duplicados:** no se puede registrar dos veces el mismo producto (mismo principio activo, marca, concentración, forma y presentación).
- **Menú:** ya aparecen Caja, Clientes, Compras, Reportes y Auditoría según los permisos del rol.
- Al iniciar, los lotes ya vencidos se marcan como «Vencido».

## Etapa 4: compras y recepción de lotes (cambios)

- **Recepción parcial:** una orden puede recibirse en varias recepciones y una línea en varios lotes («Agregar otro lote»). La orden
  pasa a *Parcial* y a *Recibida* cuando se completa. Nunca se acepta recibir más de lo pendiente.
- **Cada recepción** guarda su documento (factura/remisión, sin repetir en la orden), sus lotes, los movimientos de inventario
  (`OC #n · Recepción #m`) y su propia cuenta por pagar con vencimiento según los días de crédito. Todo en una transacción.
- **Lógica de lotes única** (`models/lotes_service.py`) para *Entradas de mercadería* y *Compras*: ya no se sobrescribe el costo de un
  lote existente (costo promedio ponderado), se conserva su proveedor y se rechazan lotes en cuarentena/vencidos/retirados o con otro vencimiento.
- **Anular orden** (solo pendiente, sin recepciones) y **Cerrar con faltante** (orden parcial), ambos con motivo y bitácora.
- Montos con `Decimal` en compras y pagos; pestaña *Recepciones* con el historial; columnas Pedido/Recibido.
- Las órdenes ya recibidas con el flujo anterior se migran como una recepción (migración 010).

Pendiente (próximas etapas): que la venta use el turno de caja, cliente y crédito (Etapa 5/6), alertas configurables (Etapa 7).
