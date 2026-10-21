"""Quarterly history of the anchor variables and supporting series.

`build()` downloads (or reads from cache) every source and returns three tables:
- anchors: one row per anchor code, one column per quarter ('2015Q1'...)
- series: supporting quarterly series for the blocks (sectors, money, budget, BoP)
- catalog: what each row is, its unit, source and how it was derived

Each recipe below is one row of the catalog, so the derivation is readable next to
the data it produces.
"""
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import pandas as pd

from macromodel.aggregate import to_quarter
from macromodel.anchors import ANCHORS
from macromodel.loaders import macrostat, minfin_index, nbu, nbu_api, nbu_monetary, worldbank

BASE_YEAR = 2021  # real GDP is expressed in average prices of this year


@dataclass
class Recipe:
    code: str
    name: str
    unit: str
    source: str
    method: str
    fn: Callable[["Data"], pd.Series]


class Data:
    """Lazy access to source frames so each dataset is downloaded once."""

    def __init__(self, cache: Path, start_year: int, refresh_from: int | None):
        self.cache, self.start, self.refresh_from = cache, start_year, refresh_from
        self.end = date.today().year
        self._nbu: dict[str, pd.DataFrame] = {}
        self._wb: dict[str, pd.Series] = {}
        self._fx = None
        self._debt = None
        self._money = None

    @property
    def macrostat(self) -> Path:
        """Andrey's MacroStat export; recipes that need it fail (and are reported) without it."""
        path = self.cache / "manual" / "MacroStat.xlsx"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found: export MacroStat from Google Sheets as .xlsx")
        return path

    def money(self) -> pd.DataFrame:
        if self._money is None:
            path = self.cache / "nbu_ms_oper.xlsx"
            if self.refresh_from is not None or not path.exists():
                path = nbu_monetary.download(self.cache)
            self._money = nbu_monetary.month_end(path)
        return self._money

    def nbu(self, name: str) -> pd.DataFrame:
        if name not in self._nbu:
            # one year back so 4-quarter sums and y/y bases exist from the first quarter
            self._nbu[name] = nbu_api.fetch(name, self.start - 1, self.end + 1, self.cache / "nbu_api", self.refresh_from)
        return self._nbu[name]

    def s(self, name: str, id_api: str, tzep: str, **dims) -> pd.Series:
        return nbu_api.select(self.nbu(name), id_api, tzep, **dims)

    def wb(self, code: str) -> pd.Series:
        if code not in self._wb:
            self._wb[code] = worldbank.indicator(code, start=self.start - 1)
        return self._wb[code]

    def fx(self) -> pd.Series:
        if self._fx is None:
            self._fx = nbu.exchange_rate(date(self.start, 1, 1), date.today())
        return self._fx

    def debt(self) -> pd.DataFrame:
        if self._debt is None:
            self._debt = minfin_index.debt_month_end(self.start, self.end)
        return self._debt


# ---------------- transformations ----------------

def q_label(s: pd.Series) -> pd.Series:
    s = s.dropna().sort_index()
    s.index = s.index.astype(str)
    return s


def m_to_q(s: pd.Series, how: str) -> pd.Series:
    """Monthly PeriodIndex series to quarters; a quarter needs all three months."""
    s = s.dropna().sort_index()
    q = s.index.asfreq("Q")
    g = s.groupby(q)
    out = {"AVG": g.mean, "END": g.last, "SUM": g.sum}[how]()
    full = g.count() == 3
    if how == "END":
        full = pd.Series([p.asfreq("M", "end") in s.index for p in out.index], index=out.index)
    return q_label(out[full])


def weighted_m_to_q(rate: pd.Series, volume: pd.Series) -> pd.Series:
    """Quarterly rate as the volume-weighted mean of monthly rates."""
    df = pd.concat({"r": rate, "v": volume}, axis=1).dropna()
    df = df[df["v"] > 0]
    g = df.assign(rv=df.r * df.v).groupby(df.index.asfreq("Q"))
    out = g.rv.sum() / g.v.sum()
    return q_label(out[g.size() == 3])


def ytd_to_q(s: pd.Series) -> pd.Series:
    """Monthly cumulative-from-January flows (budget execution) to quarterly flows.

    Uses only the quarter-end months, so a missing month inside a quarter does not
    shift flows between quarters: Q_n = YTD(end of Q_n) - YTD(end of Q_n-1).
    """
    s = s.dropna().sort_index()
    ends = s[[p.month % 3 == 0 for p in s.index]]
    ends.index = ends.index.asfreq("Q")
    prev = pd.Series([ends.get(p - 1) if p.quarter > 1 else 0.0 for p in ends.index], index=ends.index, dtype=float)
    return q_label((ends - prev).dropna())


def ytd_avg_to_q(s: pd.Series) -> pd.Series:
    """Year-to-date averages (LFS: 'average for the period, cumulative') to quarter averages.

    Q_n = n*YTD_n - (n-1)*YTD_{n-1} within each year.
    """
    s = s.dropna().sort_index()
    n = pd.Series([p.quarter for p in s.index], index=s.index)
    prev = s.groupby(s.index.year).shift(1)
    out = n * s - (n - 1) * prev
    out[n == 1] = s[n == 1]
    return out.dropna()


def chain_real(nominal: pd.Series, yoy: pd.Series, base_year: int = BASE_YEAR) -> pd.Series:
    """Real level in average prices of `base_year` from nominal levels and y/y real growth.

    Base-year quarters equal nominal; other quarters chain through the same quarter of
    the neighbouring year: X_t = X_{t-4} * (1 + g_t/100).
    """
    nominal, yoy = nominal.sort_index(), yoy.sort_index()
    real = {p: nominal[p] for p in nominal.index if p.year == base_year}
    for p in sorted(p for p in yoy.index if p.year > base_year):
        prev = p - 4
        if prev in real:
            real[p] = real[prev] * (1 + yoy[p] / 100)
    for p in sorted((p for p in yoy.index if p.year < base_year), reverse=True):
        nxt = p + 4
        if nxt in real and nxt in yoy.index:
            real[p] = real[nxt] / (1 + yoy[nxt] / 100)
    return pd.Series(real).sort_index()


def annual_to_q(s: pd.Series, how: str) -> pd.Series:
    """Annual values onto quarters: AVG/END repeat the value, SUM splits it in four."""
    out = {}
    for y, v in s.dropna().items():
        for qn in range(1, 5):
            out[f"{y}Q{qn}"] = v / 4 if how == "SUM" else v
    return pd.Series(out)


# ---------------- anchors ----------------

def _gdp(d: Data, approach: str = "ps") -> tuple[pd.Series, pd.Series]:
    nom = d.s("gdp_q", f"ea_gdp_{approach}_gdp_cp", "F_")
    yoy = d.s("gdp_q", f"ea_gdp_{approach}_gdp_cp", "PC_C_3")
    return nom, yoy


def _gdp_real(d: Data, approach: str = "ps") -> pd.Series:
    return q_label(chain_real(*_gdp(d, approach)))


# Price indices in the API are already percent changes (PCCM_ y/y, PCPM_ m/m);
# -99 marks a month not yet published.
def _pct(s: pd.Series) -> pd.Series:
    return s.mask(s == -99)


def _cpi(d, tzep="PCCM_"):
    return _pct(d.s("prices_m", "prices_price_cpi_", tzep, mcrd081="Total", ku="None"))


def _ppi(d, tzep="PCCM_"):
    return _pct(d.s("prices_m", "prices_price_ppi_", tzep, mcrk110="BCDE"))


def _bop(d, id_api, t023="#", s181="0"):
    return d.s("bop_m", id_api, "D021USD_7", freq="M", t023=t023, s181=s181)


def _budget(d, id_api, level="SBU"):
    return ytd_to_q(d.s("budget_m", id_api, "F_M_VC", mcr200p=level))


def _budget_rev(d):
    """Reported revenue; where the API stops (after 2024Q1), revenue = expenditure + net lending - financing."""
    rep = _budget(d, "gf_budgtr_Total_2")
    calc = _budget(d, "gf_budgtee_Total") + _budget(d, "gf_budgtl_Total") - _budget(d, "gf_budgtfd_total")
    return rep.combine_first(calc[calc.index > rep.index.max()])


def _rate(d, name, id_api):
    kw = dict(odr030="01", odkodter="total", ods180="total", odk111="total", odf074="total")
    r = d.s(name, id_api, "f_m_ir", **kw)
    v = d.s(name, id_api, "f_m_v", **kw)
    return weighted_m_to_q(r, v)


def _lfs(d, id_api):
    return ytd_avg_to_q(d.s("labour_q", id_api, "C_THP"))


def _fin_received(d):
    parts = [
        _bop(d, "GG_L_an_sec"),                     # net new external liabilities of government
        _bop(d, "Rez_Loans_IMF_L_an"),              # IMF credit (government and NBU), net
        _bop(d, "Sec_income_GG", t023="1"),         # grants to government
        _bop(d, "Cap_transf_GG", t023="1"),         # capital transfers incl. debt forgiveness
    ]
    return m_to_q(pd.concat(parts, axis=1).sum(axis=1, min_count=4), "SUM")


def _debt_gdp(d):
    debt = m_to_q(d.debt()["total"], "END")
    gdp4 = q_label(d.s("gdp_q", "ea_gdp_ps_gdp_cp", "F_")).rolling(4).sum()
    return (debt / gdp4 * 100).dropna()


def _cfc(d):
    pct = d.wb("NY.ADJ.DKAP.GN.ZS")
    gni = d.wb("NY.GNP.MKTP.CN") / 1e6
    return annual_to_q((pct / 100 * gni).dropna(), "SUM")


def _elec(d):
    kwh = d.wb("EG.USE.ELEC.KH.PC") * d.wb("SP.POP.TOTL") / 1e6
    return annual_to_q(kwh.dropna(), "SUM")


def _wage(d):
    """Monthly Gosstat wages from the API; quarters the API skips (2022-2023, 2024H2) from
    the quarterly figures in MacroStat, only up to the last quarter the API covers."""
    api = m_to_q(d.s("labour_m", "lmss_fund_pay_wage", "N_ONE", mcrk110="TOTAL"), "AVG")
    try:
        ms = macrostat.wages_q(d.macrostat)
    except FileNotFoundError:
        return api
    gaps = ms[(ms.index <= api.index.max()) & ~ms.index.isin(api.index)]
    return pd.concat([api, gaps]).sort_index()


def _unemp(d):
    lfs = (_lfs(d, "lmss_actnas_up1570ap_") / _lfs(d, "lmss_actnas_eap1570ap_") * 100)
    return q_label(lfs)


ANCHOR_RECIPES = [
    Recipe("GDP_REAL", "", "", "НБУ API (Госстат)", f"Номинальный ВВП {BASE_YEAR} г., сцепленный через реальный рост г/г (PC_C_3); внутригодовую динамику сравнивать только г/г", lambda d: _gdp_real(d, "ps")),
    Recipe("GDP_REAL_P", "", "", "НБУ API (Госстат)", "Как GDP_REAL: ВВП производственным методом", lambda d: _gdp_real(d, "ps")),
    Recipe("GDP_REAL_E", "", "", "НБУ API (Госстат)", "ВВП методом расходов, тот же способ сцепления", lambda d: _gdp_real(d, "es")),
    Recipe("GDP_NOM", "", "", "НБУ API (Госстат)", "ea_gdp_ps_gdp_cp, F_", lambda d: q_label(_gdp(d)[0])),
    Recipe("DEFL", "", f"{BASE_YEAR}=100", "расчёт", "GDP_NOM / GDP_REAL × 100; сезонный рисунок от сцепления, сравнивать г/г", lambda d: q_label(_gdp(d)[0]) / _gdp_real(d) * 100),
    Recipe("CPI_YOY", "", "", "НБУ API (Госстат)", "ИПЦ, % к тому же месяцу прошлого года, последний месяц квартала", lambda d: m_to_q(_cpi(d), "END")),
    Recipe("PPI_YOY", "", "", "НБУ API (Госстат)", "ИЦП промышленности (BCDE), % г/г, последний месяц квартала", lambda d: m_to_q(_ppi(d), "END")),
    Recipe("FX_AVG", "", "", "НБУ (официальный курс)", "Среднее дневных значений", lambda d: to_quarter(d.fx(), "AVG")),
    Recipe("FX_EOP", "", "", "НБУ (официальный курс)", "Последний день квартала", lambda d: to_quarter(d.fx(), "END")),
    Recipe("NBU_RATE", "", "", "НБУ API", "KEY_PolicyRate, последний день квартала", lambda d: to_quarter(_key(d), "END")),
    Recipe("LOAN_RATE", "", "", "НБУ API", "Новые кредиты резидентам (кроме банков) в гривне, средневзвешенная по объёмам", lambda d: _rate(d, "loan_rates_m", "New_Loans_Res")),
    Recipe("DEP_RATE", "", "", "НБУ API", "Новые депозиты резидентов (кроме банков) в гривне, средневзвешенная по объёмам", lambda d: _rate(d, "dep_rates_m", "New_Deposits_Res")),
    Recipe("POP", "", "", "Всемирный банк (оценка)", "SP.POP.TOTL, годовое значение на все кварталы; вся Украина по оценке ВБ, не подконтрольная территория", lambda d: annual_to_q(d.wb("SP.POP.TOTL") / 1e6, "AVG")),
    Recipe("EMPL", "", "", "НБУ API (Госстат, ОРС)", "Занятые 15–70, из накопленных средних; обследование прекращено после 2021", lambda d: q_label(_lfs(d, "lmss_actnas_ep1570ap_"))),
    Recipe("UNEMP", "", "", "НБУ API (Госстат, ОРС)", "Безработные / экономически активные 15–70; после 2021 нет данных", _unemp),
    Recipe("WAGE_NOM", "", "", "НБУ API (Госстат); пропуски из MacroStat", "Средняя месячная зарплата, среднее за квартал; 2022–2023 и 2024Q3–Q4 из квартальных данных Госстата (лист Salary)", _wage),
    Recipe("EXP_USD", "", "", "НБУ API (платёжный баланс)", "Товары и услуги, кредит, сумма месяцев", lambda d: m_to_q(_bop(d, "G_S", t023="1"), "SUM")),
    Recipe("IMP_USD", "", "", "НБУ API (платёжный баланс)", "Товары и услуги, дебет, сумма месяцев", lambda d: m_to_q(_bop(d, "G_S", t023="2"), "SUM")),
    Recipe("TRADE_BAL", "", "", "расчёт", "EXP_USD − IMP_USD", lambda d: m_to_q(_bop(d, "G_S", t023="1") - _bop(d, "G_S", t023="2"), "SUM")),
    Recipe("RES_USD", "", "", "НБУ API", "Официальные резервные активы на конец квартала", lambda d: m_to_q(d.s("reserves_m", "RES_OffReserveAssets", "T071USD_7"), "END")),
    Recipe("GFCF", "", "", "НБУ API (Госстат)", "ea_gdp_es_gfcf, F_", lambda d: q_label(d.s("gdp_q", "ea_gdp_es_gfcf", "F_"))),
    Recipe("CFC", "", "", "Всемирный банк (оценка)", "NY.ADJ.DKAP.GN.ZS × ВНД, годовое значение поровну на кварталы; ряд заканчивается 2021", _cfc),
    Recipe("BUDGET_DEF", "", "", "НБУ API (Казначейство)", "Финансирование госбюджета (дефицит «+»), из накопленных с начала года", lambda d: _budget(d, "gf_budgtfd_total")),
    Recipe("FIN_NEED_USD", "", "", "расчёт", "Считается в блоке B6", lambda d: pd.Series(dtype=float)),
    Recipe("FIN_RECEIVED_USD", "", "", "НБУ API (платёжный баланс)", "Чистые внешние обязательства госуправления + кредиты МВФ (нетто) + гранты и капитальные трансферты госуправлению", _fin_received),
    Recipe("FIN_GAP_USD", "", "", "расчёт", "FIN_NEED_USD − FIN_RECEIVED_USD, считается в блоке B6", lambda d: pd.Series(dtype=float)),
    Recipe("DEBT_GDP", "", "", "Минфин (index.minfin.com.ua)", "Государственный и гарантированный долг на конец квартала / сумма номинального ВВП за 4 квартала", _debt_gdp),
    Recipe("ELEC_CONS", "", "", "Всемирный банк (оценка)", "EG.USE.ELEC.KH.PC × население, годовое поровну на кварталы; до 2024, вся Украина", _elec),
    Recipe("FREIGHT", "", "", "Госстат (MacroStat, лист SectorIndexes M)", "Перевезено грузов за месяц, сумма за квартал; ряд с 2018", lambda d: m_to_q(macrostat.freight_m(d.macrostat), "SUM")),
]


def _key(d: Data) -> pd.Series:
    s = d.s("key_rates_d", "KEY_PolicyRate", "T90")
    s.index = s.index.to_timestamp()
    return s


# ---------------- supporting series ----------------

GVA = {"A": "сельское хозяйство", "B": "добыча", "C": "переработка", "D": "энергетика",
       "F": "строительство", "G": "торговля", "H": "транспорт", "J": "ИКТ", "O": "госуправление и оборона"}
GDP_E = {"hh": "потребление домохозяйств", "gen_gov": "потребление госуправления", "gfcf": "ВНОК",
         "ci": "изменение запасов", "egs": "экспорт", "igs": "импорт"}


def _series_recipes() -> list[Recipe]:
    r = []
    for k, nm in GVA.items():
        r.append(Recipe(f"GVA_{k}_NOM", f"ВДС: {nm}", "млн грн", "НБУ API (Госстат)", "ea_gdp_ps_gv_add F_",
                        lambda d, k=k: q_label(d.s("gdp_q", "ea_gdp_ps_gv_add", "F_", mcrk110=k))))
        r.append(Recipe(f"GVA_{k}_YOY", f"ВДС: {nm}, реальный рост", "% г/г", "НБУ API (Госстат)", "ea_gdp_ps_gv_add PC_C_3",
                        lambda d, k=k: q_label(d.s("gdp_q", "ea_gdp_ps_gv_add", "PC_C_3", mcrk110=k))))
    r.append(Recipe("GDP_REAL_YOY", "Реальный ВВП, рост", "% г/г", "НБУ API (Госстат)", "ea_gdp_ps_gdp_cp PC_C_3",
                    lambda d: q_label(_gdp(d)[1])))
    for k, nm in GDP_E.items():
        r.append(Recipe(f"GDPE_{k.upper()}_NOM", f"ВВП по расходам: {nm}", "млн грн", "НБУ API (Госстат)", f"ea_gdp_es_{k} F_",
                        lambda d, k=k: q_label(d.s("gdp_q", f"ea_gdp_es_{k}", "F_"))))
        if k != "ci":
            r.append(Recipe(f"GDPE_{k.upper()}_YOY", f"ВВП по расходам: {nm}, реальный рост", "% г/г", "НБУ API (Госстат)", f"ea_gdp_es_{k} PC_C_3",
                            lambda d, k=k: q_label(d.s("gdp_q", f"ea_gdp_es_{k}", "PC_C_3"))))
    r += [
        Recipe("COMP_EMPL", "Оплата труда наёмных работников", "млн грн", "НБУ API (Госстат)", "ea_gdp_is_emp_comp F_",
               lambda d: q_label(d.s("gdp_q", "ea_gdp_is_emp_comp", "F_"))),
        Recipe("CPI_QOQ", "ИПЦ, квартал к кварталу", "%", "НБУ API (Госстат)", "Произведение месячных индексов",
               lambda d: _qoq(_cpi(d, "PCPM_"))),
        Recipe("CORE_CPI_YOY", "Базовая инфляция", "% г/г", "НБУ API (Госстат)", "prices_price_ci_ PCCM_, конец квартала",
               lambda d: m_to_q(_pct(d.s("prices_m", "prices_price_ci_", "PCCM_", mcrd081="Total")), "END")),
        Recipe("IND_PROD_YOY", "Промышленное производство", "% г/г", "НБУ API (Госстат)", "ea_indust_ind_indprod BCDE PCCM_, среднее за квартал минус 100",
               lambda d: m_to_q(d.s("activity_m", "ea_indust_ind_indprod", "PCCM_", mcrk110="BCDE") - 100, "AVG")),
        Recipe("RETAIL_YOY", "Оборот розницы предприятий, сопоставимые цены", "% г/г", "НБУ API (Госстат)", "ea_trade_rte_ PCCM_, среднее за квартал минус 100",
               lambda d: m_to_q(d.s("activity_m", "ea_trade_rte_", "PCCM_", mcrk110="TOTAL") - 100, "AVG")),
        Recipe("CONSTR_YOY", "Строительная продукция", "% г/г", "НБУ API (Госстат)", "ea_building_index_co_ PCCM_, среднее за квартал минус 100",
               lambda d: m_to_q(d.s("activity_m", "ea_building_index_co_", "PCCM_", mcrk110="TOTAL") - 100, "AVG")),
        Recipe("M0", "Наличные вне банков (M0)", "млн грн", "НБУ API", "Конец квартала",
               lambda d: m_to_q(d.s("money_m", "M0", "t070_7", k076="Total"), "END")),
        Recipe("M3", "Денежная масса M3", "млн грн", "НБУ API", "Конец квартала",
               lambda d: m_to_q(d.s("money_m", "M3", "t070_7", k076="Total"), "END")),
        Recipe("LOAN_RATE_NFC", "Ставка по новым кредитам нефинансовым корпорациям, грн", "%", "НБУ API", "Средневзвешенная по объёмам",
               lambda d: _rate(d, "loan_rates_m", "New_Loans_NFinCorp")),
        Recipe("LOAN_RATE_HH", "Ставка по новым кредитам домохозяйствам, грн", "%", "НБУ API", "Средневзвешенная по объёмам",
               lambda d: _rate(d, "loan_rates_m", "New_Loans_Households")),
        Recipe("DEP_RATE_HH", "Ставка по новым депозитам домохозяйств, грн", "%", "НБУ API", "Средневзвешенная по объёмам",
               lambda d: _rate(d, "dep_rates_m", "New_Deposits_Households")),
        Recipe("BUDGET_REV", "Доходы госбюджета", "млн грн", "НБУ API (Казначейство)",
               "gf_budgtr_Total_2 из накопленных; после 2024Q1 API не публикует доходы, они = расходы + кредитование − финансирование",
               _budget_rev),
        Recipe("BUDGET_EXP", "Расходы госбюджета", "млн грн", "НБУ API (Казначейство)", "gf_budgtee_Total, из накопленных",
               lambda d: _budget(d, "gf_budgtee_Total")),
        Recipe("BUDGET_DEFENCE", "Расходы госбюджета на оборону", "млн грн", "НБУ API (Казначейство)", "gf_budgtef_0200, из накопленных",
               lambda d: _budget(d, "gf_budgtef_0200")),
        Recipe("CA_USD", "Текущий счёт", "млн USD", "НБУ API (платёжный баланс)", "Сальдо, сумма месяцев",
               lambda d: m_to_q(_bop(d, "Cur_acc", t023="total"), "SUM")),
        Recipe("GRANTS_USD", "Гранты госуправлению (вторичный доход)", "млн USD", "НБУ API (платёжный баланс)", "Sec_income_GG кредит",
               lambda d: m_to_q(_bop(d, "Sec_income_GG", t023="1"), "SUM")),
        Recipe("REMIT_USD", "Частные трансферты (переводы)", "млн USD", "НБУ API (платёжный баланс)", "Sec_income_FNC_PT кредит",
               lambda d: m_to_q(_bop(d, "Sec_income_FNC_PT", t023="1"), "SUM")),
        Recipe("FDI_L_USD", "Прямые инвестиции в Украину, чистые", "млн USD", "НБУ API (платёжный баланс)", "FDI_L",
               lambda d: m_to_q(_bop(d, "FDI_L"), "SUM")),
        Recipe("NBU_FX_INTERV_USD", "Чистые интервенции НБУ (+ покупка)", "млн USD", "НБУ API", "VolumNbuICM_BalPerM / 1e6",
               lambda d: m_to_q(d.s("fx_market_m", "VolumNbuICM_BalPerM", "T071USD") / 1e6, "SUM")),
        Recipe("EXT_DEBT_USD", "Валовой внешний долг", "млн USD", "НБУ API", "ED, конец квартала",
               lambda d: q_label(d.s("ext_debt_q", "ED", "T071USD_7"))),
        Recipe("EXT_DEBT_GG_USD", "Внешний долг госуправления", "млн USD", "НБУ API", "ED_GG, конец квартала",
               lambda d: q_label(d.s("ext_debt_q", "ED_GG", "T071USD_7"))),
        Recipe("DEBT_UAH", "Государственный и гарантированный долг", "млн грн", "Минфин (index.minfin.com.ua)", "Конец квартала",
               lambda d: m_to_q(d.debt()["total"], "END")),
        Recipe("REG_UNEMP", "Зарегистрированные безработные, конец квартала", "тыс. человек", "ГЦЗ (MacroStat, лист Salary)", "Конец квартала",
               lambda d: m_to_q(macrostat.registered_unemployed_m(d.macrostat), "END")),
        Recipe("EXT_FIN_GROSS_USD", "Валовое внешнее финансирование бюджета", "млн USD", "MacroStat, лист Help (Минфин)",
               "Строка TOTAL: 2022–2023 годовые суммы поровну на кварталы, с 2024 по месяцам",
               lambda d: _past(macrostat.external_financing_q(d.macrostat))),
        Recipe("DEBT_PAY_UAH", "Платежи по госдолгу (обслуживание + погашение)", "млн грн", "MacroStat, лист Debt (Минфин)",
               "Сумма месяцев; с 2022", lambda d: _past(m_to_q(macrostat.debt_payments_m(d.macrostat)["total"] * 1000, "SUM"))),
        Recipe("DEBT_PAY_EXT_UAH", "Платежи по внешнему госдолгу", "млн грн", "MacroStat, лист Debt (Минфин)",
               "Всего минус внутренний долг, сумма месяцев; 2024Q3 включает реструктуризацию еврооблигаций",
               lambda d: _past(m_to_q(macrostat.debt_payments_m(d.macrostat)["external"] * 1000, "SUM"))),
        Recipe("MONETARY_BASE", "Денежная база", "млн грн", "НБУ (ms_oper.xlsx)", "Конец квартала",
               lambda d: m_to_q(d.money()["MONETARY_BASE"], "END")),
        Recipe("NBU_CD", "Депозитные сертификаты НБУ (избыток ликвидности)", "млн грн", "НБУ (ms_oper.xlsx)", "Конец квартала",
               lambda d: m_to_q(d.money()["NBU_CD"], "END")),
        Recipe("NIR_USD", "Чистые международные резервы", "млн USD", "НБУ (ms_oper.xlsx)", "Конец квартала",
               lambda d: m_to_q(d.money()["NIR_USD"], "END")),
        Recipe("WB_UNEMP", "Безработица, модельная оценка МОТ", "%", "Всемирный банк", "SL.UEM.TOTL.ZS, годовое на все кварталы",
               lambda d: annual_to_q(d.wb("SL.UEM.TOTL.ZS"), "AVG")),
    ]
    return r


def _past(s: pd.Series) -> pd.Series:
    """Drop quarters that have not ended: sheets carry schedules and plans forward."""
    return s[s.index < str(pd.Period(date.today(), "Q"))]


def _qoq(mom: pd.Series) -> pd.Series:
    f = 1 + mom.dropna() / 100
    g = f.groupby(f.index.asfreq("Q"))
    out = g.prod() * 100 - 100
    return q_label(out[g.count() == 3])


SERIES_RECIPES = _series_recipes()


# ---------------- build ----------------

def _run(recipes: list[Recipe], d: Data, first: str, last: str) -> tuple[pd.DataFrame, list[dict], list[str]]:
    rows, cat, errors = {}, [], []
    for rc in recipes:
        try:
            s = rc.fn(d)
        except Exception as e:  # one broken source must not stop the rest
            errors.append(f"{rc.code}: {e}")
            s = pd.Series(dtype=float)
        s = s[(s.index >= first) & (s.index <= last)] if len(s) else s
        rows[rc.code] = s
        cat.append({"code": rc.code, "name": rc.name, "unit": rc.unit, "source": rc.source, "method": rc.method,
                    "first": s.dropna().index.min() if s.notna().any() else "",
                    "last": s.dropna().index.max() if s.notna().any() else "",
                    "n": int(s.notna().sum())})
    table = pd.DataFrame(rows).T
    table = table.reindex(columns=sorted(table.columns))
    table.index.name = "code"
    return table, cat, errors


def build(cache: Path, start_year: int = 2015, refresh_from: int | None = None):
    d = Data(cache, start_year, refresh_from)
    first, last = f"{start_year}Q1", str(pd.Period(date.today(), "Q"))
    for rc in ANCHOR_RECIPES:
        a = next(a for a in ANCHORS if a.code == rc.code)
        rc.name, rc.unit = a.name, rc.unit or a.unit
    anchors, cat_a, err_a = _run(ANCHOR_RECIPES, d, first, last)
    series, cat_s, err_s = _run(SERIES_RECIPES, d, first, last)
    catalog = pd.DataFrame([{**c, "table": "anchors"} for c in cat_a] + [{**c, "table": "series"} for c in cat_s])
    return anchors, series, catalog, err_a + err_s


def debt_schedule(cache: Path) -> pd.DataFrame:
    """MinFin annual debt payment schedule (UAH billion) for the financing-need block."""
    return macrostat.debt_schedule_y(Data(cache, 2015, None).macrostat)
