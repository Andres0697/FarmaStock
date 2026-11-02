-- Revierte 007. Atención: elimina los datos de recetas_venta, monto_recibido y fecha_anulacion.
DROP TABLE IF EXISTS recetas_venta;
-- @skip_if: SELECT IF(COUNT(*)=0,1,0) FROM information_schema.table_constraints WHERE table_schema=DATABASE() AND table_name='desviaciones_fefo' AND constraint_name='fk_desv_producto'
ALTER TABLE desviaciones_fefo DROP FOREIGN KEY fk_desv_producto;
-- @skip_if: SELECT IF(COUNT(*)=0,1,0) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='desviaciones_fefo' AND column_name='producto_id'
ALTER TABLE desviaciones_fefo DROP COLUMN producto_id;
-- @skip_if: SELECT IF(COUNT(*)=0,1,0) FROM information_schema.table_constraints WHERE table_schema=DATABASE() AND table_name='ventas' AND constraint_name='fk_ventas_anulada_por'
ALTER TABLE ventas DROP FOREIGN KEY fk_ventas_anulada_por;
-- @skip_if: SELECT IF(COUNT(*)=0,1,0) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='ventas' AND column_name='fecha_anulacion'
ALTER TABLE ventas DROP COLUMN fecha_anulacion;
-- @skip_if: SELECT IF(COUNT(*)=0,1,0) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='ventas' AND column_name='monto_recibido'
ALTER TABLE ventas DROP COLUMN monto_recibido;
