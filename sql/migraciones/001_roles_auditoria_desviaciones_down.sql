DROP TABLE IF EXISTS desviaciones_fefo;
DROP TABLE IF EXISTS bitacora_auditoria;
DELETE FROM usuarios WHERE usuario='regente' AND id NOT IN (SELECT usuario_id FROM ventas) AND id NOT IN (SELECT usuario_id FROM movimientos_inventario);
UPDATE usuarios SET rol='Vendedor' WHERE rol='Regente';
ALTER TABLE usuarios MODIFY rol ENUM('Administrador','Vendedor') NOT NULL;
