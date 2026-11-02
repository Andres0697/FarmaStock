-- Revierte 010. Las órdenes parciales vuelven a "Pendiente" (se pierde el detalle de recepciones).
-- @skip_if: SELECT IF(COUNT(*)=0,1,0) FROM information_schema.table_constraints WHERE table_schema=DATABASE() AND table_name='cuentas_por_pagar' AND constraint_name='fk_cxp_recepcion'
ALTER TABLE cuentas_por_pagar DROP FOREIGN KEY fk_cxp_recepcion;
-- @skip_if: SELECT IF(COUNT(*)=0,1,0) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='cuentas_por_pagar' AND column_name='recepcion_id'
ALTER TABLE cuentas_por_pagar DROP COLUMN recepcion_id;
DROP TABLE IF EXISTS recepcion_detalle;
DROP TABLE IF EXISTS recepciones_compra;
UPDATE ordenes_compra SET estado = 'Pendiente' WHERE estado = 'Parcial';
ALTER TABLE ordenes_compra MODIFY estado ENUM('Pendiente','Recibida','Anulada') NOT NULL DEFAULT 'Pendiente';
