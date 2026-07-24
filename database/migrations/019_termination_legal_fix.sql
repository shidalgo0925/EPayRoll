-- Liquidación legal v3: preaviso completo, régimen indemnización, fundamento
ALTER TABLE termination_cases
    ADD COLUMN IF NOT EXISTS regimen_indemnizacion VARCHAR(1) NOT NULL DEFAULT 'C',
    ADD COLUMN IF NOT EXISTS tipo_contrato VARCHAR(40),
    ADD COLUMN IF NOT EXISTS es_indefinido BOOLEAN,
    ADD COLUMN IF NOT EXISTS fecha_notificacion_preaviso DATE,
    ADD COLUMN IF NOT EXISTS es_tecnico BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS preaviso_formalizado BOOLEAN,
    ADD COLUMN IF NOT EXISTS fundamento_indemnizacion TEXT;

COMMENT ON COLUMN termination_cases.regimen_indemnizacion IS 'Art. 225 escala B o C';
COMMENT ON COLUMN termination_cases.fundamento_indemnizacion IS 'Override indemnización condicional (ej. suspensión prolongada)';
