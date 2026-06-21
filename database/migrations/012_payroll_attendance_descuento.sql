-- Descuento por tardanza / salida anticipada (asistencia) en ajustes de corrida

ALTER TABLE payroll_run_adjustments
    ADD COLUMN IF NOT EXISTS descuento_minutos INTEGER NOT NULL DEFAULT 0;

ALTER TABLE payroll_run_adjustments
    ADD COLUMN IF NOT EXISTS monto_desc_tiempo NUMERIC(14, 2) NOT NULL DEFAULT 0;
