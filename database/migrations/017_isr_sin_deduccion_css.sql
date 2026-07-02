-- ISR planilla: gravable = bruto×13 (sin restar CSS antes de tabla Art. 700)
UPDATE isr_config
SET deduccion_previa = 'ninguna',
    updated_at = now()
WHERE vigencia_hasta IS NULL;
