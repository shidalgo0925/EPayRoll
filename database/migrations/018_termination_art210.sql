-- Art. 210 CT: campos adicionales para liquidación completa
ALTER TABLE termination_cases
    ADD COLUMN IF NOT EXISTS monto_salario_pendiente NUMERIC(14, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS notas TEXT,
    ADD COLUMN IF NOT EXISTS documento_ref TEXT,
    ADD COLUMN IF NOT EXISTS detalle_lineas JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN termination_cases.monto_salario_pendiente IS 'Salario pendiente digitado por contador';
COMMENT ON COLUMN termination_cases.notas IS 'Notas / beneficiario (muerte) u observaciones';
COMMENT ON COLUMN termination_cases.documento_ref IS 'Referencia documento (mutuo acuerdo)';
COMMENT ON COLUMN termination_cases.detalle_lineas IS 'Snapshot de líneas de liquidación';
