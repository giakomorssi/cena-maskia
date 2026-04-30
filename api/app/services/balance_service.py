"""Domain services for the Fantacalcio league.

- SanctionService: classifies a balance result into sanction levels.
- BalanceImportService: parses an uploaded Excel/CSV bilancio,
  computes ammortamenti per fascia, plus/minus, totale costi/ricavi,
  utile/perdita and the resulting sanction.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Iterable, Optional

import pandas as pd

from app.config import settings

# ============================================================
# Sanctions
# ============================================================


@dataclass
class SanctionResult:
    level: str  # "none" | "light" | "medium" | "heavy"
    points: int
    notes: str


class SanctionService:
    """Classify utile (positive=ok, negative=loss) into a sanction level."""

    @staticmethod
    def evaluate(utile: float) -> SanctionResult:
        if utile >= 0:
            return SanctionResult("none", 0, "Bilancio in pareggio o utile.")
        loss = abs(utile)
        if loss <= settings.sanction_light_threshold:
            return SanctionResult(
                "light", 1, f"Perdita lieve ({loss:.2f}). -1 punto in classifica."
            )
        if loss <= settings.sanction_medium_threshold:
            return SanctionResult(
                "medium",
                3,
                f"Perdita media ({loss:.2f}). -3 punti in classifica e riduzione rosa di 1 slot.",
            )
        if loss <= settings.sanction_heavy_threshold:
            return SanctionResult(
                "heavy",
                6,
                f"Perdita grave ({loss:.2f}). -6 punti e riduzione rosa di 2 slot.",
            )
        return SanctionResult(
            "heavy",
            10,
            f"Perdita gravissima ({loss:.2f}). -10 punti e blocco mercato di riparazione.",
        )


# ============================================================
# Ammortamenti per fascia
# ============================================================

from app.services.player_finance_rules import amortization_pct_from_fascia


def amortization_pct(fascia: str) -> float:
    """Return the amortization percentage for a fascia label.

    Accepted forms include the configured fascia labels or numeric strings
    interpreted as the player acquisition cost.
    """
    return amortization_pct_from_fascia(fascia)


# ============================================================
# Excel / CSV parsing
# ============================================================

# Expected sheets in the workbook (any subset is fine; missing sheets are
# treated as empty). For CSV, the file is loaded as a single "ricavi" sheet
# unless it contains a `section` column.
EXPECTED_SHEETS = ("ricavi", "costi", "ammortamenti", "plus_minus")


@dataclass
class ParsedEntry:
    section: str
    label: str
    amount: float
    meta: Optional[dict] = None


@dataclass
class ParsedBalance:
    entries: list[ParsedEntry]
    total_ricavi: float
    total_costi: float
    total_ammortamenti: float
    total_plus_minus: float
    utile: float


class BalanceImportService:
    """Parse Excel/CSV uploaded by an admin into a ParsedBalance."""

    @staticmethod
    def parse(file_bytes: bytes, filename: str) -> ParsedBalance:
        name = (filename or "").lower()
        sheets: dict[str, pd.DataFrame] = {}

        if name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
            if "section" in df.columns:
                for sec, group in df.groupby(df["section"].str.lower()):
                    sheets[sec] = group
            else:
                sheets["ricavi"] = df
        else:
            xls = pd.ExcelFile(io.BytesIO(file_bytes))
            for sheet_name in xls.sheet_names:
                key = sheet_name.strip().lower().replace(" ", "_")
                sheets[key] = pd.read_excel(xls, sheet_name=sheet_name)

        entries: list[ParsedEntry] = []
        totals = {"ricavi": 0.0, "costi": 0.0, "ammortamenti": 0.0, "plus_minus": 0.0}

        for section in EXPECTED_SHEETS:
            df = sheets.get(section)
            if df is None or df.empty:
                continue
            cols = {c.lower().strip(): c for c in df.columns}

            for _, row in df.iterrows():
                label = str(
                    row.get(cols.get("label") or cols.get("voce") or "", "")
                ).strip()
                if not label or label.lower() == "nan":
                    continue

                if section == "ammortamenti":
                    cost = _to_float(
                        row.get(cols.get("costo") or cols.get("amount") or "")
                    )
                    fascia = str(row.get(cols.get("fascia") or "", "")).strip()
                    pct = amortization_pct(fascia) if fascia else 1.0
                    amount = cost * pct
                    entries.append(
                        ParsedEntry(
                            section=section,
                            label=label,
                            amount=amount,
                            meta={"costo": cost, "fascia": fascia, "pct": pct},
                        )
                    )
                    totals["ammortamenti"] += amount
                elif section == "plus_minus":
                    valore = _to_float(
                        row.get(cols.get("valore_cessione") or cols.get("amount") or "")
                    )
                    libro = _to_float(row.get(cols.get("valore_libro") or "0"))
                    delta = valore - libro
                    entries.append(
                        ParsedEntry(
                            section=section,
                            label=label,
                            amount=delta,
                            meta={"valore_cessione": valore, "valore_libro": libro},
                        )
                    )
                    totals["plus_minus"] += delta
                else:
                    amount = _to_float(
                        row.get(cols.get("amount") or cols.get("importo") or "")
                    )
                    entries.append(
                        ParsedEntry(section=section, label=label, amount=amount)
                    )
                    totals[section] += amount

        utile = (
            totals["ricavi"]
            + totals["plus_minus"]
            - totals["costi"]
            - totals["ammortamenti"]
        )

        return ParsedBalance(
            entries=entries,
            total_ricavi=totals["ricavi"],
            total_costi=totals["costi"],
            total_ammortamenti=totals["ammortamenti"],
            total_plus_minus=totals["plus_minus"],
            utile=utile,
        )

    @staticmethod
    def build_template_xlsx() -> bytes:
        """Return an empty Excel template with the expected sheets/columns."""
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            pd.DataFrame(
                {"label": ["Capitale sociale", "Sponsor", "Premi"], "amount": [0, 0, 0]}
            ).to_excel(writer, sheet_name="ricavi", index=False)
            pd.DataFrame(
                {"label": ["Stipendi", "Costi stadio", "Multe"], "amount": [0, 0, 0]}
            ).to_excel(writer, sheet_name="costi", index=False)
            pd.DataFrame(
                {"label": ["Giocatore X"], "costo": [0], "fascia": ["1-9"]}
            ).to_excel(writer, sheet_name="ammortamenti", index=False)
            pd.DataFrame(
                {"label": ["Cessione Y"], "valore_cessione": [0], "valore_libro": [0]}
            ).to_excel(writer, sheet_name="plus_minus", index=False)
        return buf.getvalue()


def _to_float(v) -> float:
    if v is None:
        return 0.0
    try:
        if isinstance(v, str):
            v = v.replace(",", ".").strip()
            if not v:
                return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0
