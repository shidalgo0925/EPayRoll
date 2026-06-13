from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from epayroll.engine.rounding import RoundingMode, round_amount

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = ROOT / "docs" / "seed" / "vacation_config.json"


@dataclass(frozen=True)
class VacationConfig:
    meses_por_periodo: int = 11
    dias_por_periodo: Decimal = Decimal("30")
    max_periodos_acumulados: int = 2
    min_dias_primer_periodo: Decimal = Decimal("15")
    alerta_planificacion_dias: int = 60
    dias_sin_planificacion_alerta: Decimal = Decimal("30")


@dataclass
class VacationBalanceResult:
    fecha_corte: date
    meses_servicio: int
    periodos_ganados: int
    dias_ganados: Decimal
    dias_gozados: Decimal
    dias_pendientes: Decimal
    excede_art59: bool
    max_dias_acumulables: Decimal
    dias_sobre_tope: Decimal
    pasivo_estimado: Decimal
    alerta_art57: bool
    alerta_mensaje: str | None = None


@dataclass
class VacationAlert:
    employee_id: str
    dias_pendientes: Decimal
    tipo: str
    mensaje: str


def load_vacation_config(path: Path | None = None) -> VacationConfig:
    cfg_path = path or DEFAULT_CONFIG
    with open(cfg_path, encoding="utf-8") as f:
        data = json.load(f)
    return VacationConfig(
        meses_por_periodo=data.get("meses_por_periodo", 11),
        dias_por_periodo=Decimal(str(data.get("dias_por_periodo", 30))),
        max_periodos_acumulados=data.get("max_periodos_acumulados", 2),
        min_dias_primer_periodo=Decimal(str(data.get("min_dias_primer_periodo", 15))),
        alerta_planificacion_dias=data.get("alerta_planificacion_dias", 60),
        dias_sin_planificacion_alerta=Decimal(str(data.get("dias_sin_planificacion_alerta", 30))),
    )


def months_of_service(fecha_inicio: date, fecha_corte: date) -> int:
    if fecha_corte < fecha_inicio:
        return 0
    months = (fecha_corte.year - fecha_inicio.year) * 12 + (fecha_corte.month - fecha_inicio.month)
    if fecha_corte.day < fecha_inicio.day:
        months -= 1
    return max(0, months)


def calc_dias_ganados(meses_servicio: int, config: VacationConfig | None = None) -> tuple[int, Decimal]:
    config = config or load_vacation_config()
    periodos = meses_servicio // config.meses_por_periodo
    dias = Decimal(str(periodos)) * config.dias_por_periodo
    return periodos, round_amount(dias, RoundingMode.CENTESIMO)


def calc_pasivo(dias_pendientes: Decimal, salario_mensual: Decimal, dias_mes: Decimal = Decimal("30")) -> Decimal:
    salario_diario = salario_mensual / dias_mes
    return round_amount(dias_pendientes * salario_diario, RoundingMode.CENTESIMO)


def check_art59(
    dias_pendientes: Decimal,
    config: VacationConfig | None = None,
) -> tuple[bool, Decimal, Decimal]:
    config = config or load_vacation_config()
    max_dias = config.dias_por_periodo * Decimal(str(config.max_periodos_acumulados))
    excede = dias_pendientes > max_dias
    sobre = max(Decimal("0"), dias_pendientes - max_dias) if excede else Decimal("0")
    return excede, max_dias, round_amount(sobre, RoundingMode.CENTESIMO)


def check_art57_alert(
    dias_pendientes: Decimal,
    proxima_vacacion_inicio: date | None,
    fecha_referencia: date,
    config: VacationConfig | None = None,
) -> tuple[bool, str | None]:
    config = config or load_vacation_config()
    if dias_pendientes < config.dias_sin_planificacion_alerta:
        return False, None

    if proxima_vacacion_inicio is None:
        return True, (
            f"Art. 57: {dias_pendientes} dias pendientes sin vacacion programada "
            f"(umbral {config.dias_sin_planificacion_alerta} dias)"
        )

    limite = fecha_referencia + timedelta(days=config.alerta_planificacion_dias)
    if proxima_vacacion_inicio > limite:
        return True, (
            f"Art. 57: vacacion programada el {proxima_vacacion_inicio.isoformat()} "
            f"supera aviso de {config.alerta_planificacion_dias} dias"
        )
    return False, None


def calculate_balance(
    fecha_inicio: date,
    fecha_corte: date,
    dias_gozados: Decimal,
    salario_mensual: Decimal,
    proxima_vacacion_inicio: date | None = None,
    config: VacationConfig | None = None,
) -> VacationBalanceResult:
    config = config or load_vacation_config()
    meses = months_of_service(fecha_inicio, fecha_corte)
    periodos, ganados = calc_dias_ganados(meses, config)
    pendientes = round_amount(ganados - dias_gozados, RoundingMode.CENTESIMO)
    excede, max_dias, sobre = check_art59(pendientes, config)
    alerta, msg = check_art57_alert(pendientes, proxima_vacacion_inicio, fecha_corte, config)
    pasivo = calc_pasivo(pendientes, salario_mensual)

    return VacationBalanceResult(
        fecha_corte=fecha_corte,
        meses_servicio=meses,
        periodos_ganados=periodos,
        dias_ganados=ganados,
        dias_gozados=dias_gozados,
        dias_pendientes=pendientes,
        excede_art59=excede,
        max_dias_acumulables=max_dias,
        dias_sobre_tope=sobre,
        pasivo_estimado=pasivo,
        alerta_art57=alerta,
        alerta_mensaje=msg,
    )
