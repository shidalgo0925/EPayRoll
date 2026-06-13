-- EPayRoll Fase 5.5 — Sustituciones vacaciones (cobertura MVP)

ALTER TABLE vacation_requests
    ADD COLUMN IF NOT EXISTS substitute_employee_id UUID REFERENCES employees(id);

CREATE INDEX IF NOT EXISTS idx_vacation_requests_substitute
    ON vacation_requests (substitute_employee_id)
    WHERE substitute_employee_id IS NOT NULL;
