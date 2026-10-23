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

from macromodel.aggregate import to_quarter, to_year
from macromodel.anchors import ANCHORS
from macromodel.loaders import gosstat, macrostat, metals, minfin_index, nbu, nbu_api, nbu_files, nbu_monetary, worldbank

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
        self._files: dict[str, Path] = {}

    @property
    def macrostat(self) -> Path:
        """Andrey's MacroStat export; recipes that need it fail (and are reported) without it."""
        path = self.cache / "manual" / "MacroStat.xlsx"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found: export MacroStat from Google Sheets as .xlsx")
        return path

    def nbu_file(self, name: str) -> Path:
        if name not in self._files:
            self._files[name] = nbu_files.path(self.cache, name, refresh=self.refresh_from is not None)
        return self._files[name]

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


def _idx(s: pd.Series) -> pd.Series:
    """Volume index (previous year = 100) to % y/y; a 0 in the API means 'no data'."""
    return s.mask(s <= 0) - 100


def _cpi(d, tzep="PCCM_"):
    return _pct(d.s("prices_m", "prices_price_cpi_", tzep, mcrd081="Total", ku="None"))


def _ppi(d, tzep="PCCM_", branch="BCDE"):
    return _pct(d.s("prices_m", "prices_price_ppi_", tzep, mcrk110=branch))


def _ppi_yoy_q(d, branch="BCDE", old="TOTAL"):
    """PPI y/y at quarter end: API from 2013; before that MacroStat (industry, end month,
    from 2011) and the NBU PPI_q file (2007-2012, quarter average, so close but not identical)."""
    out = m_to_q(_ppi(d, branch=branch), "END")
    if branch == "BCDE":
        try:
            ms = m_to_q(macrostat.cpi_extra_yoy(d.macrostat)["PPI"] - 100, "END")
            out = out.combine_first(ms)
        except FileNotFoundError:
            pass
    old_q = nbu_files.ppi_q(d.nbu_file("ppi_q"))
    if old in old_q:
        out = out.combine_first(q_label(old_q[old].rename(index=str)))
    return out.sort_index()


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
    """Monthly Gosstat wages from the API (from 2013); 2010-2012 and months the API skips
    from the NBU Wages_m file; quarters still missing (2022-2023, 2024H2) from the quarterly
    figures in MacroStat, only from 2022 (its earlier rows disagree with Gosstat) and only
    up to the last quarter the API covers."""
    api = m_to_q(d.s("labour_m", "lmss_fund_pay_wage", "N_ONE", mcrk110="TOTAL"), "AVG")
    out = api.combine_first(m_to_q(nbu_files.wages_m(d.nbu_file("wages_m")), "AVG"))
    try:
        ms = macrostat.wages_q(d.macrostat)
    except FileNotFoundError:
        return out
    gaps = ms[(ms.index >= "2022Q1") & (ms.index <= api.index.max()) & ~ms.index.isin(out.index)]
    return pd.concat([out, gaps]).sort_index()


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
    Recipe("PPI_YOY", "", "", "НБУ API (Госстат); до 2013 MacroStat и НБУ PPI_q", "ИЦП промышленности (BCDE), % г/г, последний месяц квартала; 2011–2012 из MacroStat (лист CPI), 2007–2010 из файла НБУ PPI_q (квартал к кварталу прошлого года)", _ppi_yoy_q),
    Recipe("FX_AVG", "", "", "НБУ (официальный курс)", "Среднее дневных значений", lambda d: to_quarter(d.fx(), "AVG")),
    Recipe("FX_EOP", "", "", "НБУ (официальный курс)", "Последний день квартала", lambda d: to_quarter(d.fx(), "END")),
    Recipe("NBU_RATE", "", "", "НБУ API", "KEY_PolicyRate, последний день квартала", lambda d: to_quarter(_key(d), "END")),
    Recipe("LOAN_RATE", "", "", "НБУ API", "Новые кредиты резидентам (кроме банков) в гривне, средневзвешенная по объёмам", lambda d: _rate(d, "loan_rates_m", "New_Loans_Res")),
    Recipe("DEP_RATE", "", "", "НБУ API", "Новые депозиты резидентов (кроме банков) в гривне, средневзвешенная по объёмам", lambda d: _rate(d, "dep_rates_m", "New_Deposits_Res")),
    Recipe("POP", "", "", "Всемирный банк (оценка)", "SP.POP.TOTL, годовое значение на все кварталы; вся Украина по оценке ВБ, не подконтрольная территория", lambda d: annual_to_q(d.wb("SP.POP.TOTL") / 1e6, "AVG")),
    Recipe("EMPL", "", "", "НБУ API (Госстат, ОРС)", "Занятые 15–70, из накопленных средних; обследование прекращено после 2021", lambda d: q_label(_lfs(d, "lmss_actnas_ep1570ap_"))),
    Recipe("UNEMP", "", "", "НБУ API (Госстат, ОРС)", "Безработные / экономически активные 15–70; после 2021 нет данных", _unemp),
    Recipe("WAGE_NOM", "", "", "НБУ API (Госстат); НБУ Wages_m.xlsx; пропуски из MacroStat", "Средняя месячная зарплата, среднее за квартал; 2010–2012 из файла НБУ Wages_m; оставшиеся пропуски 2022–2024 из квартальных данных Госстата (лист Salary)", _wage),
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
        Recipe("IND_PROD_YOY", "Промышленное производство", "% г/г", "НБУ API (Госстат); 2010–2012 MacroStat", "ea_indust_ind_indprod BCDE PCCM_, среднее за квартал минус 100; до 2013 лист SectorIndexes M",
               _ind_prod),
        Recipe("RETAIL_YOY", "Оборот розницы предприятий, сопоставимые цены", "% г/г", "НБУ API (Госстат)", "ea_trade_rte_ PCCM_, среднее за квартал минус 100",
               lambda d: m_to_q(_idx(d.s("activity_m", "ea_trade_rte_", "PCCM_", mcrk110="TOTAL")), "AVG")),
        Recipe("CONSTR_YOY", "Строительная продукция", "% г/г", "НБУ API (Госстат)", "ea_building_index_co_ PCCM_, среднее за квартал минус 100",
               lambda d: m_to_q(_idx(d.s("activity_m", "ea_building_index_co_", "PCCM_", mcrk110="TOTAL")), "AVG")),
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
        Recipe("STAFF_EMPL", "Среднеучётная численность штатных работников", "тыс. человек", "НБУ Number_m.xlsx (Госстат, предприятия)",
               "Среднее за квартал; с 2010; продолжается после 2021, когда ОРС прекращено (без ФЛП и малых предприятий)",
               lambda d: m_to_q(nbu_files.staff_m(d.nbu_file("staff_m")), "AVG")),
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


def _ind_prod(d):
    api = m_to_q(_idx(d.s("activity_m", "ea_indust_ind_indprod", "PCCM_", mcrk110="BCDE")), "AVG")
    try:
        ms = m_to_q(macrostat.industry_yoy_m(d.macrostat) - 100, "AVG")
    except FileNotFoundError:
        return api
    return api.combine_first(ms).sort_index()


# Industry branches in the NBU API (mcrk110), Gosstat KVED-2010 groups
IND_BRANCHES = {
    "B": "добыча", "B1": "добыча угля", "B2": "добыча нефти и газа", "B3": "добыча металлических руд",
    "C": "переработка", "C1": "пищевая промышленность", "C4": "кокс и нефтепереработка", "C5": "химия",
    "C7": "резина, пластмассы, неметаллические минералы", "C8": "металлургия и металлоизделия (24–25)",
    "C9": "машиностроение", "D": "энергетика (электроэнергия, газ, пар)",
}

# CPI groups (COICOP) in the API; mcrd081 code -> (code suffix, name)
CPI_GROUPS = {"01": ("FOOD", "продукты питания и безалкогольные напитки"), "02": ("ALC_TOB", "алкоголь и табак"),
              "04": ("UTIL", "жильё, вода, электроэнергия, газ"), "06": ("HEALTH", "здравоохранение"),
              "07": ("TRANSPORT", "транспорт")}

# CPI items only MacroStat has (from 2010, so y/y from 2011)
CPI_DETAIL = {"ELEC": "электроэнергия", "GAS": "природный газ", "HEAT": "горячая вода, отопление",
              "WATER": "водоснабжение", "FUEL": "топливо и масла"}


def _yoy_from_mom(mom: pd.Series) -> pd.Series:
    """% y/y from monthly indices to the previous month (=100): product of the last 12."""
    f = (mom.dropna() / 100).sort_index()
    full = f.rolling(12).count() == 12
    full &= pd.Series([f.index[i] - 11 == f.index[i - 11] if i >= 11 else False for i in range(len(f))], index=f.index)
    return (f.rolling(12).apply(lambda x: x.prod(), raw=True) * 100 - 100)[full]


def _trade(d, sheet, key):
    return m_to_q(nbu_files.trade_groups_m(d.nbu_file("trade_m"), sheet)[key], "SUM")


def _extra_recipes() -> list[Recipe]:
    r = []
    for k, nm in IND_BRANCHES.items():
        r.append(Recipe(f"IND_{k}_YOY", f"Промпроизводство: {nm}", "% г/г", "НБУ API (Госстат)",
                        f"ea_indust_ind_indprod {k} PCCM_, среднее за квартал минус 100; с 2013",
                        lambda d, k=k: m_to_q(_idx(d.s("activity_m", "ea_indust_ind_indprod", "PCCM_", mcrk110=k)), "AVG")))
    r.append(Recipe("PPI_METAL_YOY", "ИЦП: металлургия и металлоизделия", "% г/г", "НБУ API (Госстат); 2007–2012 НБУ PPI_q",
                    "prices_price_ppi_ C8 PCCM_, конец квартала; до 2013 «Металургійне виробництво» из PPI_q",
                    lambda d: _ppi_yoy_q(d, "C8", "METALS")))
    r.append(Recipe("PPI_MINING_YOY", "ИЦП: добыча", "% г/г", "НБУ API (Госстат); 2007–2012 НБУ PPI_q",
                    "prices_price_ppi_ B PCCM_, конец квартала", lambda d: _ppi_yoy_q(d, "B", "MINING")))
    for code, (suf, nm) in CPI_GROUPS.items():
        r.append(Recipe(f"CPI_{suf}_YOY", f"ИПЦ: {nm}", "% г/г", "НБУ API (Госстат)", f"prices_price_cpi_ {code} PCCM_, конец квартала",
                        lambda d, code=code: m_to_q(_pct(d.s("prices_m", "prices_price_cpi_", "PCCM_", mcrd081=code, ku="None")), "END")))
    for k, nm in CPI_DETAIL.items():
        r.append(Recipe(f"CPI_{k}_YOY", f"ИПЦ: {nm}", "% г/г", "MacroStat (лист CPI, Госстат)",
                        "Произведение 12 месячных индексов, конец квартала; с 2011",
                        lambda d, k=k: m_to_q(_yoy_from_mom(macrostat.cpi_items_mom(d.macrostat)[k]), "END")))
    for k in nbu_files.TRADE_GROUPS:
        if k == "TOTAL":
            continue
        r.append(Recipe(f"EXPG_{k}_USD", f"Экспорт товаров: {k.lower()}", "млн USD", "НБУ (Trade_m.xlsx, платёжный баланс)",
                        "Сумма месяцев; товарные группы по КПБ6", lambda d, k=k: _trade(d, "1.1", k)))
        r.append(Recipe(f"IMPG_{k}_USD", f"Импорт товаров: {k.lower()}", "млн USD", "НБУ (Trade_m.xlsx, платёжный баланс)",
                        "Сумма месяцев; товарные группы по КПБ6", lambda d, k=k: _trade(d, "1.2", k)))
    for k in macrostat.AGRO_PRICES:
        r.append(Recipe(f"PX_{k}_USD", f"Экспортная цена FOB Черное море: {k.lower()}", "USD/т", "MacroStat (лист AGROTrends)",
                        "Среднее месячных цен за квартал", lambda d, k=k: m_to_q(macrostat.agro_export_prices_m(d.macrostat)[k], "AVG")))
    for k in macrostat.BUDGET_ROWS:
        r.append(Recipe(f"CB_{k}", f"Сводный бюджет: {k.lower()}", "млн грн", "MacroStat (лист Budget, Казначейство)",
                        "Накопленные с начала года, переведены в кварталы; с 2011",
                        lambda d, k=k: _past(ytd_to_q(macrostat.budget_consolidated_ytd(d.macrostat)[k]))))
    r.append(Recipe("CB_DEFSEC", "Сводный бюджет: оборона + общественный порядок и безопасность", "млн грн",
                    "MacroStat (лист Budget, Казначейство)", "Функциональные коды 0200 + 0300, из накопленных",
                    lambda d: _past(ytd_to_q(macrostat.budget_consolidated_ytd(d.macrostat)[["EXP_DEFENCE", "EXP_ORDER"]].sum(axis=1, min_count=2)))))
    for k, nm in METALS.items():
        r.append(Recipe(k, f"Производство: {nm}", "тыс. т", "Укрметалургпром (GMK Center, пресса); data/external/metals_m.csv",
                        "Сумма месяцев; с 2024, вносится вручную", lambda d, k=k: m_to_q(metals.monthly()[k], "SUM")))
    for pre, file, nm, unit in (("INFL_EXP", "surveys_price", "Инфляционные ожидания на 12 мес.", "%"),
                                ("FX_EXP", "surveys_rate", "Ожидаемый курс через 12 мес.", "грн за USD")):
        for k, who in SURVEY_WHO.items():
            r.append(Recipe(f"{pre}_{k}", f"{nm}: {who}", unit, f"НБУ {file.title()}.xlsx (опросы)",
                            "Среднее опросов квартала (группы опрашиваются с разной частотой); с 2013",
                            lambda d, f=file, k=k: _q_mean(nbu_files.surveys_m(d.nbu_file(f))[k])))
    return r


METALS = {"STEEL_KT": "сталь", "PIG_IRON_KT": "чугун", "ROLLED_KT": "прокат"}
SURVEY_WHO = {"BANKS": "банки", "BUSINESS": "предприятия", "HH": "домохозяйства", "ANALYSTS": "финансовые аналитики"}


def _q_mean(s: pd.Series) -> pd.Series:
    """Mean of whatever months of the quarter have a value (for surveys run once a quarter)."""
    s = s.dropna()
    return q_label(s.groupby(s.index.asfreq("Q")).mean())


SERIES_RECIPES = _series_recipes() + _extra_recipes()


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


# ---------------- annual history ----------------
#
# Estimation on annual data needs years before the quarterly API starts (2010). Each
# annual row is the quarterly series rolled up where all four quarters exist; earlier
# years come from an annual source listed in ANNUAL_FALLBACK, and the catalog says from
# which year the roll-up takes over.

STOCKS = {"RES_USD", "M0", "M3", "EXT_DEBT_USD", "EXT_DEBT_GG_USD", "DEBT_UAH", "REG_UNEMP",
          "MONETARY_BASE", "NBU_CD", "NIR_USD", "FX_EOP", "NBU_RATE", "DEBT_GDP"}


def annual_agg(code: str) -> str:
    """How a quarterly row rolls up into a year: anchors say so themselves; for the other
    rows end-of-period measures (stocks, y/y price indices) take Q4, flows the sum and the
    rest (rates, volume y/y, prices) the mean."""
    a = next((a for a in ANCHORS if a.code == code), None)
    if a:
        return a.agg
    if code in STOCKS or (code.startswith(("CPI_", "PPI_", "CORE_CPI")) and code.endswith("_YOY")):
        return "END"
    if code.endswith(("_NOM", "_USD", "_UAH", "_KT")) or code.startswith(("CB_", "BUDGET_", "COMP_EMPL")):
        return "SUM" if not code.startswith("PX_") else "AVG"
    return "AVG"


def _gdp_y(d):
    return nbu_files.gdp_y(d.nbu_file("gdp_y"))


def _wb_y(code, scale=1.0):
    return lambda d: d.wb(code) * scale


# code -> (source, method, fn(d) -> Series indexed by year)
ANNUAL_FALLBACK = {
    "GDP_NOM": ("НБУ GDP_y.xlsx (Госстат, СНС 2008)", "Номинальный ВВП за год", lambda d: _gdp_y(d)["GDP_NOM"]),
    "CPI_YOY": ("Всемирный банк", "До 2007 нет декабрьских данных: среднегодовой ИПЦ (FP.CPI.TOTL.ZG)", _wb_y("FP.CPI.TOTL.ZG")),
    "LOAN_RATE": ("Всемирный банк", "FR.INR.LEND, средняя ставка по кредитам (все валюты и сроки, старые операции тоже)", _wb_y("FR.INR.LEND")),
    "DEP_RATE": ("Всемирный банк", "FR.INR.DPST, средняя ставка по депозитам", _wb_y("FR.INR.DPST")),
    "EXP_USD": ("Всемирный банк (платёжный баланс)", "BX.GSR.GNFS.CD / 1e6", _wb_y("BX.GSR.GNFS.CD", 1e-6)),
    "IMP_USD": ("Всемирный банк (платёжный баланс)", "BM.GSR.GNFS.CD / 1e6", _wb_y("BM.GSR.GNFS.CD", 1e-6)),
    "TRADE_BAL": ("Всемирный банк (платёжный баланс)", "BN.GSR.GNFS.CD / 1e6", _wb_y("BN.GSR.GNFS.CD", 1e-6)),
    "GFCF": ("Всемирный банк", "NE.GDI.FTOT.CN / 1e6", _wb_y("NE.GDI.FTOT.CN", 1e-6)),
    "WAGE_NOM": ("НБУ Wages_y.xlsx (Госстат)", "Среднемесячная зарплата за год", lambda d: nbu_files.wages_y(d.nbu_file("wages_y"))),
}

# annual-only rows: code -> (name, unit, source, method, fn)
ANNUAL_ONLY = {
    "GDP_REAL_YOY": ("Реальный ВВП, рост", "% г/г", "НБУ GDP_y.xlsx (Госстат)", "Официальный годовой индекс физического объёма минус 100", lambda d: _gdp_y(d)["GDP_REAL_IDX"] - 100),
    "DEFL_YOY": ("Дефлятор ВВП, рост", "% г/г", "НБУ GDP_y.xlsx (Госстат)", "Индекс-дефлятор минус 100", lambda d: _gdp_y(d)["DEFL_IDX"] - 100),
    "CPI_AVG_YOY": ("ИПЦ, среднегодовой", "% г/г", "Всемирный банк", "FP.CPI.TOTL.ZG", _wb_y("FP.CPI.TOTL.ZG")),
    "WB_HH_CONS_YOY": ("Потребление домохозяйств, реальный рост", "% г/г", "Всемирный банк", "NE.CON.PRVT.KD.ZG", _wb_y("NE.CON.PRVT.KD.ZG")),
    "WB_GFCF_YOY": ("ВНОК, реальный рост", "% г/г", "Всемирный банк", "NE.GDI.FTOT.KD.ZG", _wb_y("NE.GDI.FTOT.KD.ZG")),
    "WB_EXP_REAL_YOY": ("Экспорт, реальный рост", "% г/г", "Всемирный банк", "NE.EXP.GNFS.KD.ZG", _wb_y("NE.EXP.GNFS.KD.ZG")),
    "WB_IMP_REAL_YOY": ("Импорт, реальный рост", "% г/г", "Всемирный банк", "NE.IMP.GNFS.KD.ZG", _wb_y("NE.IMP.GNFS.KD.ZG")),
    "WB_AGR_YOY": ("ВДС сельского хозяйства, реальный рост", "% г/г", "Всемирный банк", "NV.AGR.TOTL.KD.ZG", _wb_y("NV.AGR.TOTL.KD.ZG")),
    "WB_IND_YOY": ("ВДС промышленности (вкл. строительство), реальный рост", "% г/г", "Всемирный банк", "NV.IND.TOTL.KD.ZG", _wb_y("NV.IND.TOTL.KD.ZG")),
    "WB_MANUF_YOY": ("ВДС переработки, реальный рост", "% г/г", "Всемирный банк", "NV.IND.MANF.KD.ZG", _wb_y("NV.IND.MANF.KD.ZG")),
    "WB_SERV_YOY": ("ВДС услуг, реальный рост", "% г/г", "Всемирный банк", "NV.SRV.TOTL.KD.ZG", _wb_y("NV.SRV.TOTL.KD.ZG")),
    "WB_CREDIT_GDP": ("Кредит частному сектору", "% ВВП", "Всемирный банк", "FS.AST.PRVT.GD.ZS; с 2008", _wb_y("FS.AST.PRVT.GD.ZS")),
}
for _k, (_unit, _old, _new) in gosstat.PRODUCTS.items():
    ANNUAL_ONLY[f"PROD_{_k}"] = (f"Производство: {_k.rsplit('_', 1)[0].lower().replace('_', ' ')}", _unit,
                                 "Госстат (stat.gov.ua)", f"«{_old}» до 2010" + (f", «{_new}» с 2011" if _new else "; после 2010 конфиденциально"),
                                 lambda d, k=_k: _prod_y(d, k))


def _prod_y(d, k: str) -> pd.Series:
    """Gosstat output; steel, pig iron and rolled products from 2016 from Ukrmetallurgprom."""
    s = gosstat.products_y(gosstat.download(d.cache, refresh=d.refresh_from is not None))[k]
    m = metals.annual()
    return s.combine_first(m[k]) if k in m else s


for _k in metals.annual().columns:
    _n, _u, _src, _meth, _fn = ANNUAL_ONLY[f"PROD_{_k}"]
    ANNUAL_ONLY[f"PROD_{_k}"] = (_n, _u, _src + "; с 2016 Укрметалургпром (GMK Center)", _meth, _fn)


def _annual_real_gdp(nom_y: pd.Series, real_q_y: pd.Series, idx: pd.Series) -> pd.Series:
    """Real GDP by year in BASE_YEAR prices: roll-up where available, earlier years chained
    back through the official annual volume index."""
    out = real_q_y.dropna().copy()
    out.index = out.index.astype(int)
    for y in sorted((y for y in idx.index if y < out.index.min()), reverse=True):
        if y + 1 in out.index and y + 1 in idx.index:
            out[y] = out[y + 1] / (idx[y + 1] / 100)
    return out.sort_index()


def build_annual(d: Data, anchors: pd.DataFrame, series: pd.DataFrame, catalog: pd.DataFrame, first_year: int):
    """Annual table (rows = codes, columns = years) and its catalog; see the note above."""
    last_year = date.today().year - 1
    years = list(range(first_year, last_year + 1))
    rows, cat, errors = {}, [], []
    base = pd.concat([anchors, series])
    for code, q in base.iterrows():
        rolled = to_year(q.dropna(), annual_agg(code))
        rolled.index = rolled.index.astype(int)
        src = catalog.set_index("code").loc[code]
        source, method = src["source"], f"Из кварталов ({annual_agg(code)}): {src['method']}"
        if code in ANNUAL_FALLBACK:
            fsrc, fmethod, fn = ANNUAL_FALLBACK[code]
            try:
                fb = fn(d)
                fb.index = fb.index.astype(int)
                start = rolled.index.min() if len(rolled) else last_year + 1
                fill = fb[fb.index < start]
                if len(fill):
                    rolled = pd.concat([fill, rolled])
                    source = f"{source}; до {start} — {fsrc}"
                    method = f"{method}. До {start}: {fmethod}"
            except Exception as e:
                errors.append(f"annual {code}: {e}")
        rows[code] = rolled
        cat.append({"code": code, "name": src["name"], "unit": src["unit"], "source": source, "method": method})
    # real GDP and the deflator need the annual chain rather than a roll-up of quarters
    try:
        g = _gdp_y(d)
        real = _annual_real_gdp(rows["GDP_NOM"], rows["GDP_REAL"], g["GDP_REAL_IDX"])
        for code in ("GDP_REAL", "GDP_REAL_P"):
            rows[code] = real
        rows["DEFL"] = (rows["GDP_NOM"] / real * 100).dropna()
        for c in cat:
            if c["code"] in ("GDP_REAL", "GDP_REAL_P"):
                c["method"] += f". До первого полного года кварталов — назад по годовому индексу физобъёма Госстата (GDP_y.xlsx)"
            if c["code"] == "DEFL":
                c["method"] = f"GDP_NOM / GDP_REAL × 100 за год ({BASE_YEAR}=100)"
    except Exception as e:
        errors.append(f"annual GDP_REAL: {e}")
    for code, (name, unit, source, method, fn) in ANNUAL_ONLY.items():
        try:
            s = fn(d)
            s.index = s.index.astype(int)
        except Exception as e:
            errors.append(f"annual {code}: {e}")
            s = pd.Series(dtype=float)
        rows[code] = s
        cat = [c for c in cat if c["code"] != code]  # an official annual figure replaces the roll-up
        cat.append({"code": code, "name": name, "unit": unit, "source": source, "method": method})
    table = pd.DataFrame({k: v.reindex(years) for k, v in rows.items()}).T
    table.index.name = "code"
    for c in cat:
        s = table.loc[c["code"]].dropna()
        c.update(first=int(s.index.min()) if len(s) else "", last=int(s.index.max()) if len(s) else "", n=len(s))
    return table, pd.DataFrame(cat), errors
