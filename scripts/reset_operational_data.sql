-- Blanqueo total: solo empleados 8-888-8888 (Juan) y 9-219-884 (Narciso).
-- Borra contratos, planilla, prestaciones, asistencia procesada y empleados de prueba.

BEGIN;

-- Exportaciones y planilla
DELETE FROM sipe_exports;
DELETE FROM dgi_exports;
DELETE FROM bank_exports;
DELETE FROM payroll_run_adjustments;
DELETE FROM payroll_lines;
DELETE FROM payroll_employee_summary;
DELETE FROM payslips;
DELETE FROM payroll_runs;
DELETE FROM payroll_periods;
DELETE FROM employee_isr_ytd;

-- Prestaciones y liquidaciones
DELETE FROM termination_cases;
DELETE FROM vacation_requests;
DELETE FROM vacation_balances;
DELETE FROM decimo_accumulations;
DELETE FROM seniority_provisions;
DELETE FROM severance_fund;

-- Asistencia
DELETE FROM attendance_daily;
DELETE FROM attendance_facts;
DELETE FROM attendance_import_batches;
DELETE FROM time_entries;
DELETE FROM absences;
DELETE FROM incapacities;
DELETE FROM employee_schedules;

-- Datos por empleado (todos, incluidos los que se conservan)
DELETE FROM employee_concept_assignments;
DELETE FROM contract_amendments;
DELETE FROM salary_changes;
DELETE FROM employee_dependents;
DELETE FROM employee_documents;
DELETE FROM employee_history;
DELETE FROM employee_bank_accounts;
DELETE FROM contracts;

-- Empleados de prueba / duplicados — conservar solo los 2 reales
DELETE FROM employees
WHERE cedula NOT IN ('8-888-8888', '9-219-884');

DELETE FROM integration_sync_log;
DELETE FROM audit_log;

COMMIT;
