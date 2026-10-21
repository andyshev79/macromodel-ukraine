"""Anchor variables: the only channel between model blocks.

Mirrors the DICT and ANCHORS sheets of the Google workbook. Change the list here
and in DICT together.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Anchor:
    code: str
    name: str
    unit: str
    block: str
    agg: str  # SUM | AVG | END: how quarters roll up into a year
    source: str


ANCHORS = [
    Anchor("GDP_REAL", "Реальный ВВП", "млн грн, цены базового года", "B1/B2", "SUM", "Госстат"),
    Anchor("GDP_REAL_P", "Реальный ВВП по производству", "млн грн, цены базового года", "B1", "SUM", "Госстат"),
    Anchor("GDP_REAL_E", "Реальный ВВП по расходам", "млн грн, цены базового года", "B2", "SUM", "Госстат"),
    Anchor("GDP_NOM", "Номинальный ВВП", "млн грн", "B3", "SUM", "Госстат"),
    Anchor("DEFL", "Дефлятор ВВП", "индекс", "B3", "AVG", "формула"),
    Anchor("CPI_YOY", "ИПЦ", "% г/г, конец периода", "B3", "END", "Госстат"),
    Anchor("PPI_YOY", "ИЦП", "% г/г, конец периода", "B3", "END", "Госстат"),
    Anchor("FX_AVG", "Курс UAH/USD, средний", "грн за USD", "B5", "AVG", "НБУ"),
    Anchor("FX_EOP", "Курс UAH/USD, конец периода", "грн за USD", "B5", "END", "НБУ"),
    Anchor("NBU_RATE", "Учётная ставка НБУ", "%", "B7", "END", "НБУ"),
    Anchor("LOAN_RATE", "Ставка по новым кредитам в гривне", "%", "B7", "AVG", "НБУ"),
    Anchor("DEP_RATE", "Ставка по новым депозитам в гривне", "%", "B7", "AVG", "НБУ"),
    Anchor("POP", "Население на подконтрольной территории", "млн человек", "B4", "AVG", "оценка"),
    Anchor("EMPL", "Занятые", "тыс. человек", "B4", "AVG", "Госстат / оценка"),
    Anchor("UNEMP", "Уровень безработицы", "%", "B4", "AVG", "Госстат / оценка"),
    Anchor("WAGE_NOM", "Средняя номинальная зарплата", "грн в месяц", "B4", "AVG", "Госстат"),
    Anchor("EXP_USD", "Экспорт товаров и услуг", "млн USD", "B5", "SUM", "НБУ"),
    Anchor("IMP_USD", "Импорт товаров и услуг", "млн USD", "B5", "SUM", "НБУ"),
    Anchor("TRADE_BAL", "Сальдо торговли", "млн USD", "B5", "SUM", "формула"),
    Anchor("RES_USD", "Международные резервы", "млн USD", "B5", "END", "НБУ"),
    Anchor("GFCF", "Валовое накопление основного капитала", "млн грн", "B2", "SUM", "Госстат"),
    Anchor("CFC", "Потребление основного капитала", "млн грн", "B8", "SUM", "Госстат"),
    Anchor("BUDGET_DEF", "Дефицит госбюджета", "млн грн", "B6", "SUM", "Минфин"),
    Anchor("FIN_NEED_USD", "Потребность во внешнем финансировании", "млн USD", "B6", "SUM", "расчёт"),
    Anchor("FIN_RECEIVED_USD", "Получено внешнего финансирования", "млн USD", "B6", "SUM", "Минфин / НБУ"),
    Anchor("FIN_GAP_USD", "Разрыв финансирования", "млн USD", "B6", "SUM", "формула"),
    Anchor("DEBT_GDP", "Госдолг", "% ВВП", "B6", "END", "Минфин"),
    Anchor("ELEC_CONS", "Потребление электроэнергии", "млн кВт·ч", "B8", "SUM", "Укрэнерго / оценка"),
    Anchor("FREIGHT", "Перевезення вантажів", "млн т", "B8", "SUM", "Госстат (MacroStat)"),
]

BY_CODE = {a.code: a for a in ANCHORS}
