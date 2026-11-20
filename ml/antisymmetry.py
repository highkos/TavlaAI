"""Renk takasi (antisimetri) olcumu ve kapisi - Faz 7-R adim 0.

Neden. F7-55 olctu: model **antisimetrik degil**. Ayni fiziksel pozisyon
+1 ve -1 bakis acisindan degerlendirildiginde `corr(e(+1), e(-1)) = -0,7019`
(cikmasi gereken -1,0), ortalama `|e(+1)+e(-1)| = 1,0044`, politika argmax'i
yalnizca 1/59 vakada ayni. Bu bir **model kusuru**, olcum gurultusu degil.

Neden R-D'den once. Damitilacak model ayni kusuru tasirsa butun R-D
sonuclari kirlenir: ogretmen etiketleri dogru olsa bile model onlari
bakisa gore farkli ogrenir. Bu yuzden R-D egitimi **iki perspektif
artirimi** (veya girdi kanoniklestirme) kullanmak zorundadir ve bu, bir
kapiyla dogrulanmalidir.

Kapi (kullanicinin belirledigi):
  * `|corr(e(+1), e(-1))| >= 0,99`
  * renk takasinda ER farki **olculemez** olmali (eslesmis GA sifiri icerir)

Ikinci kosul nokta tahminine degil GA'ya bakar (Kural 3).

Onemli ayrim. Iki farkli donusum vardir ve karistirilmamalidir:

``mirror_vector``
    **Renk takasi (fiziksel aynalama).** Tahta aynalanir, bakis isaret
    doner. Vektoruzer renk-simetriktir, yani bu donusum vektorde yalnizca
    **goreli kup sahibini** isaret dondurur. Bu, girdinin renk-simetrik
    oldugunun kanitidir; modelin kusuru girdiden **gelmez**.
``flip_perspective``
    **Ayni tahta, karsi bakis.** Nokta bloklari `ACTIVE <-> OPP` yer
    degistirir ve her blok icinde 24 nokta blogu ters cevrilir (bloklar
    "haneden cikisa uzaklik" ile indekslenir). **Kapi bu donusumu kullanir:**
    ayni fiziksel pozisyon iki bakistan degerlendirilir; antisimetrik
    modelde `e(-1) = -e(+1)` olur.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

import gnubg_er

#: Kullanicinin belirledigi korelasyon kapisi.
CORR_MIN = 0.99

#: Eslesmis fark GA'si icin yeniden ornekleme.
BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261122

#: `|e(+1) + e(-1)|` icin "esdeger" tolerans. Antisimetrik modelde tam 0'dir;
#: 1e-3, olcum yuvarlamasinin cok uzerinde ama gercek kusurun cok altindadir.
SUM_TOL = 1e-3

#: Varsayilan cikti yollari.
ANTISYMMETRY_PATH = "ml/artifacts/antisymmetry.json"
ANTISYMMETRY_MD_PATH = "ml/artifacts/antisymmetry.md"

#: Nokta bloklari: 24 blok x 4 noron.
_POINT_BLOCKS = 24
_BLOCK_WIDTH = 4
_AWAY_WIDTH = gnubg_er.OPP_AWAY - gnubg_er.ACTIVE_AWAY


class AntisymmetryError(RuntimeError):
    """Olcum yapilamadi."""


# ----------------------------------------------------------------------
# Aynalama
# ----------------------------------------------------------------------


def mirror_board(board: Sequence[int]) -> list[int]:
    """Tahtayi perspektif degistirerek aynalar (Beyaz <-> Siyah).

    `board[0]` = Beyaz bar, `board[1..24]` = 1..24, `board[25]` = Siyah bar;
    pozitif = Beyaz. Aynalamada Beyaz'in `i` hanesi Siyah'in `i` hanesine
    duser, yani `25 - i`'ye ve isaret ters doner.
    """
    if len(board) < 26:
        raise AntisymmetryError("board en az 26 eleman olmali: %d" % len(board))
    out = [0] * 26
    out[0] = -int(board[25])
    out[25] = -int(board[0])
    for i in range(1, 25):
        out[i] = -int(board[25 - i])
    return out


def mirror_vector(vector: Sequence[float]) -> list[float]:
    """221'lik girdi vektorunde **renk takasinin** etkisi.

    Vektoruzer renk-simetriktir: `ACTIVE_*` bloklari oynayan tarafin,
    `OPP_*` bloklari rakibin; aynalama + bakis cevirmede ikisi de ayni
    kaliyor. Geriye yalnizca **goreli** kup sahibi kaliyor, o da isaret
    dondurur.

    Yani `vectorize(mirror_board(b), bo, wo, white_score=bs,
    black_score=ws, perspective=-turn) == mirror_vector(vectorize(b, wo,
    bo, white_score=ws, black_score=bs, perspective=turn))`. Bu, girdinin
    antisimetrik oldugunun kanitidir; `test_antisymmetry.py` 500 rastgele
    vakada dogrular.
    """
    if len(vector) != gnubg_er.VECTOR_SIZE:
        raise AntisymmetryError(
            "vektor %d eleman olmali: %d" % (gnubg_er.VECTOR_SIZE, len(vector))
        )
    out = [float(v) for v in vector]
    out[gnubg_er.CUBE_OWNER] = -out[gnubg_er.CUBE_OWNER]
    return out


def _reverse_point_blocks(vector: Sequence[float], base: int) -> list[float]:
    """Bir 96'lik nokta blogunu `j -> 25 - j` ile ters cevirir."""
    out = [0.0] * (_POINT_BLOCKS * _BLOCK_WIDTH)
    for j in range(1, _POINT_BLOCKS + 1):
        src = base + _BLOCK_WIDTH * (25 - j - 1)
        dst = _BLOCK_WIDTH * (j - 1)
        out[dst : dst + _BLOCK_WIDTH] = [float(v) for v in vector[src : src + _BLOCK_WIDTH]]
    return out


def flip_perspective(vector: Sequence[float]) -> list[float]:
    """221'lik girdi vektorunu **ayni tahtada karsi bakisa** cevirir.

    Nokta bloklari `ACTIVE <-> OPP` yer degistirir **ve** her blok icinde
    24 nokta blogu ters cevrilir: bloklar "haneden cikisa uzaklik" ile
    indekslenir (`j = 25 - point` Beyaz icin, `j = point` Siyah icin), bu
    yuzden duz bir blok takasi yetmez.

    Skaler noronlar (bar, off, pip, escaped, away) yer degistirir; kup
    sahibi isaret doner; para/Crawford/contact bayraklari ayni kalir.

    `flip_perspective(flip_perspective(v)) == v` (girisim).
    """
    if len(vector) != gnubg_er.VECTOR_SIZE:
        raise AntisymmetryError(
            "vektor %d eleman olmali: %d" % (gnubg_er.VECTOR_SIZE, len(vector))
        )
    out = [float(v) for v in vector]
    a, o = gnubg_er.ACTIVE_OFFSET, gnubg_er.OPP_OFFSET
    width = _POINT_BLOCKS * _BLOCK_WIDTH
    out[a : a + width] = _reverse_point_blocks(vector, o)
    out[o : o + width] = _reverse_point_blocks(vector, a)
    for left, right in (
        (gnubg_er.ACTIVE_BAR, gnubg_er.OPP_BAR),
        (gnubg_er.ACTIVE_OFF, gnubg_er.OPP_OFF),
        (gnubg_er.ACTIVE_PIP, gnubg_er.OPP_PIP),
        (gnubg_er.ACTIVE_ESC, gnubg_er.OPP_ESC),
    ):
        out[left], out[right] = float(vector[right]), float(vector[left])
    out[gnubg_er.CUBE_OWNER] = -float(vector[gnubg_er.CUBE_OWNER])
    la, lo = gnubg_er.ACTIVE_AWAY, gnubg_er.OPP_AWAY
    out[la : la + _AWAY_WIDTH] = [float(v) for v in vector[lo : lo + _AWAY_WIDTH]]
    out[lo : lo + _AWAY_WIDTH] = [float(v) for v in vector[la : la + _AWAY_WIDTH]]
    return out


def augment_perspectives(
    cases: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Her vakayi **iki** perspektifle dondurur (R-D egitim artirimi).

    Donen liste `2 * len(cases)` elemanlidir ve **ciftler bitisiktir**:
    `[vaka0(+1), vaka0(-1), vaka1(+1), vaka1(-1), ...]`. Her eleman
    `perspective` (+1 / -1) ve `valueSign` (+1 / -1) alanlarini tasir.

    * `perspective` girdi vektorunun hangi bakistan uretilecegini soyler
      (``gnubg_er.vectorize(..., perspective=case["perspective"])``).
    * `valueSign` deger hedefinin isaretini soyler: ayni fiziksel pozisyon
      karsi bakistan degerlendirildiginde equity **isaret doner**.

    Politika hedefi (en iyi aday indeksi) **degismez**: adaylar ayni
    fiziksel afterstate'lerdir, yalnizca vektorleri bakisa gore yazilir.

    **Kural 7:** bu fonksiyon yalnizca veri hacmini degistirir; baska hicbir
    parametre degismez. Ayni pozisyon iki kez gorunur, bu **kasitlidir**:
    modelin iki bakista tutarli olmasi hedeflenir.
    """
    out: list[dict[str, Any]] = []
    for case in cases:
        turn = int(case["turn"])
        for perspective in (turn, -turn):
            item = dict(case)
            item["perspective"] = perspective
            item["valueSign"] = 1.0 if perspective == turn else -1.0
            out.append(item)
    return out


# ----------------------------------------------------------------------
# Olcum
# ----------------------------------------------------------------------


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape[0] < 2:
        return float("nan")
    am = a - a.mean()
    bm = b - b.mean()
    denom = float(np.sqrt(np.sum(am * am) * np.sum(bm * bm)))
    if denom <= 0.0:
        return float("nan")
    return float(np.sum(am * bm) / denom)


def _bootstrap_ci(
    values: Sequence[float], *, resamples: int, seed: int
) -> tuple[float, float]:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    for b in range(resamples):
        idx = rng.integers(0, arr.shape[0], size=arr.shape[0])
        draws[b] = float(np.mean(arr[idx]))
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


@dataclass
class AntisymmetryReport:
    """Renk takasi olcumunun tamami."""

    count: int = 0
    correlation: float = float("nan")
    mean_abs_sum: float = float("nan")
    max_abs_sum: float = float("nan")
    sum_within_tol: int = 0
    sum_total: int = 0
    vectorizer_checked: int = 0
    vectorizer_mismatches: int = 0
    argmax_agreement: int = 0
    argmax_total: int = 0
    er_plus: float = float("nan")
    er_minus: float = float("nan")
    er_diff: float = float("nan")
    er_diff_ci_low: float = float("nan")
    er_diff_ci_high: float = float("nan")
    er_diff_excludes_zero: bool = False
    corr_min: float = CORR_MIN
    sum_tol: float = SUM_TOL
    model: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def argmax_rate(self) -> float:
        if self.argmax_total == 0:
            return float("nan")
        return self.argmax_agreement / float(self.argmax_total)

    @property
    def vectorizer_symmetric(self) -> bool:
        """Girdi vektoru renk-simetrik mi (kusur modelde mi, girdide mi)?"""
        return self.vectorizer_checked > 0 and self.vectorizer_mismatches == 0

    @property
    def corr_ok(self) -> bool:
        return math.isfinite(self.correlation) and abs(self.correlation) >= self.corr_min

    @property
    def er_ok(self) -> bool:
        """Renk takasinda ER farki **olculemez** olmali (GA sifiri icerir)."""
        return not self.er_diff_excludes_zero

    @property
    def passed(self) -> bool:
        return self.corr_ok and self.er_ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "model": self.model,
            "correlation": self.correlation,
            "meanAbsSum": self.mean_abs_sum,
            "maxAbsSum": self.max_abs_sum,
            "sumWithinTol": self.sum_within_tol,
            "sumTotal": self.sum_total,
            "vectorizerChecked": self.vectorizer_checked,
            "vectorizerMismatches": self.vectorizer_mismatches,
            "vectorizerSymmetric": self.vectorizer_symmetric,
            "argmaxAgreement": self.argmax_agreement,
            "argmaxTotal": self.argmax_total,
            "argmaxRate": self.argmax_rate,
            "erPlus": self.er_plus,
            "erMinus": self.er_minus,
            "erDiff": self.er_diff,
            "erDiffCiLow": self.er_diff_ci_low,
            "erDiffCiHigh": self.er_diff_ci_high,
            "erDiffExcludesZero": self.er_diff_excludes_zero,
            "corrMin": self.corr_min,
            "sumTol": self.sum_tol,
            "corrOk": self.corr_ok,
            "erOk": self.er_ok,
            "passed": self.passed,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AntisymmetryReport":
        """``to_dict`` ciktisindan geri kurar.

        Olcum gnubg ile dakikalar surer; kaydedilmis bir raporu yeniden
        **bicimlendirmek** icin olcumu tekrarlamak gerekmesin.
        """
        return cls(
            count=int(data.get("count", 0)),
            correlation=float(data.get("correlation", float("nan"))),
            mean_abs_sum=float(data.get("meanAbsSum", float("nan"))),
            max_abs_sum=float(data.get("maxAbsSum", float("nan"))),
            sum_within_tol=int(data.get("sumWithinTol", 0)),
            sum_total=int(data.get("sumTotal", 0)),
            vectorizer_checked=int(data.get("vectorizerChecked", 0)),
            vectorizer_mismatches=int(data.get("vectorizerMismatches", 0)),
            argmax_agreement=int(data.get("argmaxAgreement", 0)),
            argmax_total=int(data.get("argmaxTotal", 0)),
            er_plus=float(data.get("erPlus", float("nan"))),
            er_minus=float(data.get("erMinus", float("nan"))),
            er_diff=float(data.get("erDiff", float("nan"))),
            er_diff_ci_low=float(data.get("erDiffCiLow", float("nan"))),
            er_diff_ci_high=float(data.get("erDiffCiHigh", float("nan"))),
            er_diff_excludes_zero=bool(data.get("erDiffExcludesZero", False)),
            corr_min=float(data.get("corrMin", CORR_MIN)),
            sum_tol=float(data.get("sumTol", SUM_TOL)),
            model=str(data.get("model", "")),
            notes=list(data.get("notes", [])),
        )


def measure_antisymmetry(
    model_path: Path,
    cases: Sequence[dict[str, Any]],
    *,
    gnubg: Path,
    plies: int = 2,
    timeout: int = 120,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    progress: bool = False,
) -> AntisymmetryReport:
    """Ayni fiziksel pozisyonlari iki bakistan degerlendirir.

    Her vaka icin:

    * `e_plus`  : afterstate'lerin deger kafasi ciktisi, `perspective = turn`
    * `e_minus` : **ayni** afterstate'lerin ciktisi, `perspective = -turn`

    Antisimetrik modelde `e_minus == -e_plus` olur. Olculenler:

    * `corr(e_plus, e_minus)` -- -1'e yakin olmali
    * `|e_plus + e_minus|` -- 0'a yakin olmali
    * politika antisimetrisi: `argmax(logit(+1)) == argmin(logit(-1))`
    * ER(+1) ve ER(-1) (gnubg hakem) ve eslesmis fark GA'si

    Hakem **bir kez** cagrilir: iki bakis da ayni fiziksel afterstate
    kumesini kullanir, dolayisiyla referans denklemleri degismez. Boylece
    olculen fark yalnizca **secim** farkidir (Kural 7).
    """
    usable, skipped = gnubg_er.split_cases(cases)
    if not usable:
        raise AntisymmetryError("kullanilabilir vaka yok")
    session = gnubg_er.GnubgSession(gnubg, plies=plies, timeout=timeout)
    scorer = gnubg_er.OnnxScorer(Path(model_path))

    plus_values: list[float] = []
    minus_values: list[float] = []
    losses_plus: list[float] = []
    losses_minus: list[float] = []
    agree = 0
    total = 0
    within_tol = 0
    vec_checked = 0
    vec_bad = 0

    for index, case in enumerate(usable, start=1):
        if progress:
            print("[%d/%d] %s" % (index, len(usable), case.get("name", "?")), file=sys.stderr)
        turn = int(case["turn"])
        after_states = case["afterStates"]
        if not after_states:
            continue

        tables = session.eval_afterstates([a["board"] for a in after_states], -turn)
        equities = [-gnubg_er._equity_at(table, plies) for table in tables]
        best_equity = max(equities)

        vec_plus = [
            gnubg_er.vectorize(
                a["board"],
                int(a.get("whiteOff", 0)),
                int(a.get("blackOff", 0)),
                perspective=turn,
            )
            for a in after_states
        ]
        vec_minus = [
            gnubg_er.vectorize(
                a["board"],
                int(a.get("whiteOff", 0)),
                int(a.get("blackOff", 0)),
                perspective=-turn,
            )
            for a in after_states
        ]

        # Girdi invaryanti: ayni tahta, karsi bakis == bakis takasi.
        for vp, vm in zip(vec_plus, vec_minus):
            vec_checked += 1
            if max(abs(x - y) for x, y in zip(flip_perspective(vp), vm)) > 1e-9:
                vec_bad += 1

        val_plus = scorer.values(vec_plus)
        val_minus = scorer.values(vec_minus)
        for vp, vm in zip(val_plus, val_minus):
            plus_values.append(float(vp))
            minus_values.append(float(vm))
            if abs(float(vp) + float(vm)) <= SUM_TOL:
                within_tol += 1

        # **F7-81:** politika kafasi icin antisimetri "ayni argmax" degildir.
        # Politika kafasi **oynayacak tarafin** en iyi hamlesini siralar.
        # Bakis cevrilince oynayacak taraf degisir, dolayisiyla dogru ifade
        # `argmax(logit(+1)) == argmin(logit(-1))` olur. Eski kod iki argmax'i
        # karsilastiriyordu; bu, model kusursuz antisimetrik olsa bile
        # uyusmazlik raporlardi.
        if scorer.policy_name is not None:
            logit_plus = scorer.logits(vec_plus)
            logit_minus = scorer.logits(vec_minus)
            pick_plus = max(range(len(logit_plus)), key=lambda i: logit_plus[i])
            pick_minus = min(range(len(logit_minus)), key=lambda i: logit_minus[i])
        else:
            pick_plus = max(range(len(val_plus)), key=lambda i: val_plus[i])
            pick_minus = min(range(len(val_minus)), key=lambda i: val_minus[i])

        total += 1
        if pick_plus == pick_minus:
            agree += 1

        losses_plus.append(best_equity - equities[pick_plus])
        losses_minus.append(best_equity - equities[pick_minus])

    if not plus_values:
        raise AntisymmetryError("hicbir afterstate degerlendirilemedi")

    a = np.asarray(plus_values, dtype=np.float64)
    b = np.asarray(minus_values, dtype=np.float64)
    sums = np.abs(a + b)

    diffs = np.asarray(losses_plus, dtype=np.float64) - np.asarray(
        losses_minus, dtype=np.float64
    )
    ci_low, ci_high = _bootstrap_ci(diffs, resamples=resamples, seed=seed)

    report = AntisymmetryReport(
        count=len(usable),
        model=str(model_path),
        correlation=_pearson(a, b),
        mean_abs_sum=float(np.mean(sums)),
        max_abs_sum=float(np.max(sums)),
        sum_within_tol=within_tol,
        sum_total=len(plus_values),
        vectorizer_checked=vec_checked,
        vectorizer_mismatches=vec_bad,
        argmax_agreement=agree,
        argmax_total=total,
        er_plus=float(np.mean(losses_plus)),
        er_minus=float(np.mean(losses_minus)),
        er_diff=float(np.mean(diffs)),
        er_diff_ci_low=ci_low,
        er_diff_ci_high=ci_high,
        er_diff_excludes_zero=bool(ci_low > 0.0 or ci_high < 0.0),
    )
    if skipped:
        report.notes.append("%d vaka atlandi (terminal/gecersiz)" % len(skipped))
    report.notes.append(
        "Girdi vektoru renk takasinda simetrikse kusur **modelde**dir; "
        "girdi simetrisi bu raporda ayrica olculur."
    )
    report.notes.append(
        "Kapi bir **teshis**tir: `|corr| >= 0.99` bu mimariyle ulasilabilir "
        "degil. Karar iki bakisli ER (F7-101) ve ppg ile verilir."
    )
    if not report.corr_ok:
        report.notes.append(
            "KORELASYON KAPISI DUSTU: |corr| = %.4f < %.2f"
            % (abs(report.correlation), CORR_MIN)
        )
    if not report.er_ok:
        report.notes.append(
            "ER FARKI KAPISI DUSTU: GA [%.4f; %.4f] sifiri disliyor" % (ci_low, ci_high)
        )
    return report


# ----------------------------------------------------------------------
# Cikarim aninda antisimetriklestirme (F7-84)
# ----------------------------------------------------------------------

SYMMETRISED_PATH = "ml/artifacts/antisymmetry_symmetrised.json"
SYMMETRISED_MD_PATH = "ml/artifacts/antisymmetry_symmetrised.md"


def symmetrise_value(e_plus: float, e_minus: float) -> float:
    """``e_hat = (f(x,+1) - f(x,-1)) / 2``.

    Antisimetrik bir modelde ``f(x,-1) = -f(x,+1)`` oldugundan bu ifade
    ``f(x,+1)``'e indirgenir; kusurlu modelde iki bakisin **ortalamasini**
    alir, yani kusuru yariya indirir. Iki ileri gecis gerektirir.

    **Ortalama degil fark.** Iki bakis ayni fiziksel pozisyonu **zit
    isaretle** puanlar; bu yuzden dogru simetrizasyon farktir. F7-55'teki
    basarisiz "naif duzeltme" logit'leri **ortaliyordu** (isaret hatasi).
    """
    return 0.5 * (float(e_plus) - float(e_minus))


def symmetrise_logits(logits_plus: Sequence[float], logits_minus: Sequence[float]) -> list[float]:
    """Politika icin ``(logit(+1) - logit(-1)) / 2``.

    Iki bakis **ayni** aday listesini siralar (adaylar hamle yapan tarafin
    afterstate'leri), dolayisiyla fark anlamlidir. Ortalama almak iki farkli
    skorlama fonksiyonunu karistirir ve siralalmayi bozar.
    """
    if len(logits_plus) != len(logits_minus):
        raise AntisymmetryError("logit uzunluklari farkli")
    return [0.5 * (float(a) - float(b)) for a, b in zip(logits_plus, logits_minus)]


class SymmetrisedReport:
    """Cikarim aninda antisimetriklestirmenin ER'ye etkisi."""

    def __init__(self, *, model: str, corpus: str, plies: int) -> None:
        self.model = model
        self.corpus = corpus
        self.plies = int(plies)
        self.cases = 0
        self.raw_policy: list[float] = []
        self.sym_policy: list[float] = []
        self.raw_value: list[float] = []
        self.sym_value: list[float] = []
        self.argmax_changed = 0
        self.notes: list[str] = []

    def _mean(self, xs: Sequence[float]) -> float:
        return float(np.mean(xs)) if xs else float("nan")

    @property
    def raw_policy_er(self) -> float:
        return self._mean(self.raw_policy)

    @property
    def sym_policy_er(self) -> float:
        return self._mean(self.sym_policy)

    @property
    def raw_value_er(self) -> float:
        return self._mean(self.raw_value)

    @property
    def sym_value_er(self) -> float:
        return self._mean(self.sym_value)

    def _paired(self, before: Sequence[float], after: Sequence[float]) -> tuple[float, float, float]:
        if not before or len(before) != len(after):
            return float("nan"), float("nan"), float("nan")
        diff = np.asarray(after, dtype=np.float64) - np.asarray(before, dtype=np.float64)
        low, high = _bootstrap_ci(diff, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED)
        return float(diff.mean()), low, high

    @property
    def policy_delta(self) -> tuple[float, float, float]:
        return self._paired(self.raw_policy, self.sym_policy)

    @property
    def value_delta(self) -> tuple[float, float, float]:
        return self._paired(self.raw_value, self.sym_value)

    @property
    def policy_improved(self) -> bool:
        _, _, high = self.policy_delta
        return bool(np.isfinite(high) and high < 0.0)

    @property
    def value_improved(self) -> bool:
        _, _, high = self.value_delta
        return bool(np.isfinite(high) and high < 0.0)

    def to_dict(self) -> dict[str, Any]:
        pd, pl, ph = self.policy_delta
        vd, vl, vh = self.value_delta
        return {
            "symmetrisedVersion": 1,
            "model": self.model,
            "corpus": self.corpus,
            "plies": self.plies,
            "cases": self.cases,
            "argmaxChanged": self.argmax_changed,
            "policy": {
                "rawEr": self.raw_policy_er,
                "symEr": self.sym_policy_er,
                "delta": pd,
                "ciLow": pl,
                "ciHigh": ph,
                "improved": self.policy_improved,
            },
            "value": {
                "rawEr": self.raw_value_er,
                "symEr": self.sym_value_er,
                "delta": vd,
                "ciLow": vl,
                "ciHigh": vh,
                "improved": self.value_improved,
            },
            "notes": list(self.notes),
        }


def measure_symmetrised(
    model_path: Path,
    cases: Sequence[dict[str, Any]],
    *,
    gnubg: Path,
    plies: int = 2,
    timeout: int = 120,
    progress: bool = False,
) -> SymmetrisedReport:
    """Ayni aday kumesini iki bakistan puanlar, sonra simetrizasyonu olcer.

    Her vaka icin:

    * ``raw``  : ``argmax(logit(+1))`` -- bugunku urun yolu
    * ``sym``  : ``argmax((logit(+1) - logit(-1)) / 2)``
    * deger icin ``raw = e(+1)``, ``sym = (e(+1) - e(-1)) / 2``

    Hakem **bir kez** cagrilir; iki kol da ayni referansi kullanir, bu yuzden
    olculen fark yalnizca **secim** farkidir (Kural 7).
    """
    usable, skipped = gnubg_er.split_cases(cases)
    if not usable:
        raise AntisymmetryError("kullanilabilir vaka yok")
    session = gnubg_er.GnubgSession(gnubg, plies=plies, timeout=timeout)
    scorer = gnubg_er.OnnxScorer(Path(model_path))
    report = SymmetrisedReport(model=str(model_path), corpus="", plies=plies)
    if skipped:
        report.notes.append("%d vaka atlandi (terminal/gecersiz)" % len(skipped))

    for index, case in enumerate(usable, start=1):
        if progress:
            print("[%d/%d] %s" % (index, len(usable), case.get("name", "?")), file=sys.stderr)
        turn = int(case["turn"])
        after_states = case["afterStates"]
        if not after_states:
            continue

        tables = session.eval_afterstates([a["board"] for a in after_states], -turn)
        equities = [-gnubg_er._equity_at(table, plies) for table in tables]
        best_equity = max(equities)

        vec_plus = [
            gnubg_er.vectorize(
                a["board"], int(a.get("whiteOff", 0)), int(a.get("blackOff", 0)),
                perspective=turn,
            )
            for a in after_states
        ]
        vec_minus = [
            gnubg_er.vectorize(
                a["board"], int(a.get("whiteOff", 0)), int(a.get("blackOff", 0)),
                perspective=-turn,
            )
            for a in after_states
        ]

        logits_plus = scorer.logits(vec_plus)
        logits_minus = scorer.logits(vec_minus)
        values_plus = scorer.values(vec_plus)
        values_minus = scorer.values(vec_minus)

        sym_logits = symmetrise_logits(logits_plus, logits_minus)
        sym_values = [
            symmetrise_value(a, b) for a, b in zip(values_plus, values_minus)
        ]

        raw_index = int(np.argmax(logits_plus))
        sym_index = int(np.argmax(sym_logits))
        if raw_index != sym_index:
            report.argmax_changed += 1

        report.raw_policy.append(best_equity - equities[raw_index])
        report.sym_policy.append(best_equity - equities[sym_index])

        raw_value_index = int(np.argmax(values_plus))
        sym_value_index = int(np.argmax(sym_values))
        report.raw_value.append(best_equity - equities[raw_value_index])
        report.sym_value.append(best_equity - equities[sym_value_index])
        report.cases += 1

    if report.cases == 0:
        raise AntisymmetryError("hicbir vaka olculemedi")
    return report


def build_symmetrised_markdown(report: SymmetrisedReport) -> str:
    pd, pl, ph = report.policy_delta
    vd, vl, vh = report.value_delta
    lines = [
        "# Faz 7-R - Cikarim aninda antisimetriklestirme",
        "",
        "Soru: **renk takasi kusurunu egitmeden, cikarimda duzeltebilir miyiz?**",
        "",
        "`e_hat = (f(x,+1) - f(x,-1)) / 2`, politika icin `(logit(+1) - logit(-1)) / 2`.",
        "Iki ileri gecis; bir ONNX cikarimi icin ihmal edilebilir maliyet.",
        "",
        "Model: `%s`" % report.model,
        "Hakem: gnubg %d-ply" % report.plies,
        "",
        "| Yol | Ham ER | Simetrik ER | Fark | %95 GA | Karar |",
        "|---|---|---|---|---|---|",
        "| `policy` | %.4f | %.4f | %+.4f | [%+.4f; %+.4f] | %s |"
        % (
            report.raw_policy_er, report.sym_policy_er, pd, pl, ph,
            "IYILESDI" if report.policy_improved else "kanitlanmadi",
        ),
        "| `value` | %.4f | %.4f | %+.4f | [%+.4f; %+.4f] | %s |"
        % (
            report.raw_value_er, report.sym_value_er, vd, vl, vh,
            "IYILESDI" if report.value_improved else "kanitlanmadi",
        ),
        "",
        "| Ayrinti | Deger |",
        "|---|---|",
        "| Vaka | %d |" % report.cases,
        "| Argmax degisen vaka | %d (%.4f) |"
        % (report.argmax_changed, report.argmax_changed / max(report.cases, 1)),
        "",
    ]
    if report.notes:
        lines.append("## Notlar")
        lines.append("")
        for note in report.notes:
            lines.append("- " + note)
        lines.append("")
    return "\n".join(lines)


def build_markdown(
    report: AntisymmetryReport, *, title: str = "Faz 7-R - Renk takasi (antisimetri)"
) -> str:
    """Insan-okur Markdown rapor (Turkce ondalik virgul)."""

    def f(value: float, digits: int = 4) -> str:
        if not math.isfinite(value):
            return "-"
        return (("%." + str(digits) + "f") % value).replace(".", ",")

    lines = ["# " + title, ""]
    lines.append("Soru: **model renk takasinda ayni seyi mi soyluyor?**")
    lines.append("")
    if report.model:
        lines.append("Model: `%s`" % report.model)
        lines.append("")
    lines.append("| Olcum | Deger | Kapi | Durum |")
    lines.append("|---|---|---|---|")
    lines.append(
        "| `corr(e(+1), e(-1))` | %s | `\\|corr\\| >= %.2f` | %s |"
        % (f(report.correlation), report.corr_min, "GECTI" if report.corr_ok else "DUSTU")
    )
    lines.append(
        "| ER farki GA | [%s; %s] | sifiri icermeli | %s |"
        % (
            f(report.er_diff_ci_low),
            f(report.er_diff_ci_high),
            "GECTI" if report.er_ok else "DUSTU",
        )
    )
    lines.append("")
    lines.append("| Ayrinti | Deger |")
    lines.append("|---|---|")
    lines.append("| Vaka | %d |" % report.count)
    lines.append(
        "| Girdi renk-simetrisi (`flip_perspective`) | %d/%d uyusmazlik |"
        % (report.vectorizer_mismatches, report.vectorizer_checked)
    )
    lines.append("| `mean \\|e(+1)+e(-1)\\|` | %s |" % f(report.mean_abs_sum))
    lines.append("| `max \\|e(+1)+e(-1)\\|` | %s |" % f(report.max_abs_sum))
    lines.append(
        "| `\\|e(+1)+e(-1)\\| <= %s` | %d/%d |"
        % (f(report.sum_tol, 3), report.sum_within_tol, report.sum_total)
    )
    lines.append(
        "| Politika antisimetrisi (`argmax(+1) == argmin(-1)`) | %d/%d (%s) |"
        % (report.argmax_agreement, report.argmax_total, f(report.argmax_rate))
    )
    lines.append("| ER(+1) | %s |" % f(report.er_plus))
    lines.append("| ER(-1) | %s |" % f(report.er_minus))
    lines.append("| ER farki | %s |" % f(report.er_diff))
    lines.append("")
    lines.append("**Karar: %s**" % ("GECTI" if report.passed else "DUSTU"))
    lines.append("")
    if report.notes:
        lines.append("## Notlar")
        lines.append("")
        for note in report.notes:
            lines.append("- " + note)
        lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="antisymmetry",
        description="Renk takasi (antisimetri) olcumu - Faz 7-R adim 0",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    measure = sub.add_parser("measure", help="modeli corpus uzerinde olc")
    measure.add_argument("--model", required=True, help="ONNX model yolu")
    measure.add_argument(
        "--cases",
        default="ml/artifacts/reference_corpus_v2.json",
        help="vaka dosyasi (varsayilan: corpus v2)",
    )
    measure.add_argument("--limit", type=int, default=0, help="ilk N vaka (0 = hepsi)")
    measure.add_argument("--stride", type=int, default=1, help="her N'inci vaka")
    measure.add_argument("--plies", type=int, default=2, help="gnubg hakem derinligi")
    measure.add_argument("--gnubg", default=None, help="gnubg-cli yolu")
    measure.add_argument("--timeout", type=int, default=120)
    measure.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    measure.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    measure.add_argument("--out", default=ANTISYMMETRY_PATH)
    measure.add_argument("--markdown", default=ANTISYMMETRY_MD_PATH)
    measure.add_argument("--progress", action="store_true")

    sym = sub.add_parser(
        "symmetrise", help="cikarim aninda antisimetriklestirmenin ER etkisi"
    )
    sym.add_argument("--model", required=True, help="ONNX model yolu")
    sym.add_argument(
        "--cases",
        default="ml/artifacts/reference_corpus_v2.json",
        help="vaka dosyasi (varsayilan: corpus v2)",
    )
    sym.add_argument("--limit", type=int, default=0, help="ilk N vaka (0 = hepsi)")
    sym.add_argument("--stride", type=int, default=1, help="her N'inci vaka")
    sym.add_argument("--plies", type=int, default=2, help="gnubg hakem derinligi")
    sym.add_argument("--gnubg", default=None, help="gnubg-cli yolu")
    sym.add_argument("--timeout", type=int, default=120)
    sym.add_argument("--out", default=SYMMETRISED_PATH)
    sym.add_argument("--markdown", default=SYMMETRISED_MD_PATH)
    sym.add_argument("--progress", action="store_true")
    return parser


def _load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ("cases", "positions", "items"):
            if key in data:
                return list(data[key])
        raise AntisymmetryError("vaka listesi bulunamadi: %s" % path)
    return list(data)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command not in ("measure", "symmetrise"):
        raise AntisymmetryError("bilinmeyen komut: %s" % args.command)

    cases = _load_cases(Path(args.cases))
    if args.stride > 1:
        cases = cases[:: args.stride]
    if args.limit > 0:
        cases = cases[: args.limit]

    gnubg = Path(args.gnubg) if args.gnubg else gnubg_er.find_gnubg()

    if args.command == "symmetrise":
        sym = measure_symmetrised(
            Path(args.model),
            cases,
            gnubg=gnubg,
            plies=args.plies,
            timeout=args.timeout,
            progress=args.progress,
        )
        sym.corpus = str(args.cases)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(sym.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        md = Path(args.markdown)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(build_symmetrised_markdown(sym) + "\n", encoding="utf-8")

        pd, pl, ph = sym.policy_delta
        vd, vl, vh = sym.value_delta
        print("vaka: %d" % sym.cases)
        print("policy: %.4f -> %.4f (%+.4f) GA [%+.4f; %+.4f] -> %s" % (
            sym.raw_policy_er, sym.sym_policy_er, pd, pl, ph,
            "IYILESDI" if sym.policy_improved else "kanitlanmadi"))
        print("value : %.4f -> %.4f (%+.4f) GA [%+.4f; %+.4f] -> %s" % (
            sym.raw_value_er, sym.sym_value_er, vd, vl, vh,
            "IYILESDI" if sym.value_improved else "kanitlanmadi"))
        print("argmax degisen: %d/%d" % (sym.argmax_changed, sym.cases))
        return 0 if (sym.policy_improved or sym.value_improved) else 1

    report = measure_antisymmetry(
        Path(args.model),
        cases,
        gnubg=gnubg,
        plies=args.plies,
        timeout=args.timeout,
        resamples=args.resamples,
        seed=args.seed,
        progress=args.progress,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md = Path(args.markdown)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(build_markdown(report) + "\n", encoding="utf-8")

    print("vaka: %d" % report.count)
    print("corr: %.4f (kapi |corr| >= %.2f) -> %s" % (
        report.correlation, report.corr_min, "GECTI" if report.corr_ok else "DUSTU"))
    print("ER farki: %.4f GA [%.4f; %.4f] -> %s" % (
        report.er_diff, report.er_diff_ci_low, report.er_diff_ci_high,
        "GECTI" if report.er_ok else "DUSTU"))
    print("karar: %s" % ("GECTI" if report.passed else "DUSTU"))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
