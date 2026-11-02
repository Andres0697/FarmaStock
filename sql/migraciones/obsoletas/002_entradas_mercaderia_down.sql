-- Deshace la migración 002 (borra el historial de entradas; los lotes ya creados se quedan).
USE farmastock;
DROP TABLE IF EXISTS entrada_detalle;
DROP TABLE IF EXISTS entradas_inventario;
