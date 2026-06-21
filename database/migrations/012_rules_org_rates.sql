-- EPayRoll — Reglas motor usan tasas variables (override por organization_legal_rates)

UPDATE calculation_rules cr
SET base_calculo = 'min(bruto_cotizable, tope_css) * tasa_css_empleado'
FROM payroll_concepts pc
WHERE pc.id = cr.concept_id AND pc.codigo = 'CSS_EMPLEADO';

UPDATE calculation_rules cr
SET base_calculo = 'bruto_cotizable_se * tasa_se_empleado'
FROM payroll_concepts pc
WHERE pc.id = cr.concept_id AND pc.codigo = 'SE_EMPLEADO';

UPDATE calculation_rules cr
SET base_calculo = 'bruto_cotizable_se * tasa_se_patronal'
FROM payroll_concepts pc
WHERE pc.id = cr.concept_id AND pc.codigo = 'SE_EMPLEADOR';
