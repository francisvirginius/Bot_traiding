"""
Entonnoir de décision — applique les 4 couches dans l'ordre :

  1. Biais macro (DFII10 + DXY)
  2. Positionnement COT
  3. Calendrier économique
  4. Signal technique (V3 Trend Rider)

Le funnel PROPOSE des trades, il n'en exécute aucun automatiquement.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from gold_bot.data import macro, cot, calendar
from gold_bot.strategy import trend_rider
from gold_bot.engine import risk
from gold_bot.strategy.trend_rider import TrendSignal

logger = logging.getLogger(__name__)


@dataclass
class FunnelResult:
    passed: bool                            # True si un trade est proposé
    stopped_at_layer: Optional[int]         # 1-4, None si toutes passées
    reason: str                             # Explication texte
    signal: Optional[TrendSignal] = None   # Signal technique (si layer 4 atteinte)
    trade_proposal: Optional[dict] = None  # Proposition complète avec sizing
    layers: dict = field(default_factory=dict)  # Résultats de chaque couche


def run(
    df_ohlcv: pd.DataFrame,
    capital: float = 10_000.0,
    risk_pct: float = 0.01,
    fred_api_key: Optional[str] = None,
    cot_zscore_threshold: float = 1.5,
    calendar_block_hours: float = 4.0,
    calendar_reduce_hours: float = 24.0,
) -> FunnelResult:
    """
    Exécute l'entonnoir de décision complet.

    Args:
        df_ohlcv: DataFrame OHLCV XAU/USD (colonnes : open, high, low, close, volume)
        capital: Capital disponible en USD
        risk_pct: Risque par trade (ex : 0.01 = 1%)
        fred_api_key: Clé API FRED (optionnel, lu depuis env si None)
        cot_zscore_threshold: Seuil z-score COT
        calendar_block_hours: Heures avant événement pour bloquer
        calendar_reduce_hours: Heures avant événement pour réduire la taille

    Returns:
        FunnelResult dataclass
    """
    ts = datetime.now(timezone.utc).isoformat()
    layers = {}

    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 1 : Biais Macro
    # ─────────────────────────────────────────────────────────────────────────
    logger.info(f"[{ts}] Couche 1 — Biais macro...")
    try:
        macro_result = macro.get_bias(api_key=fred_api_key)
    except Exception as e:
        logger.error(f"Erreur layer 1 (macro) : {e}")
        macro_result = macro.MacroBias(
            bias="NEUTRE",
            dfii10_trend=0.0,
            dxy_trend=0.0,
            details={"error": str(e)},
        )

    layers["macro"] = {
        "bias": macro_result.bias,
        "dfii10_trend": macro_result.dfii10_trend,
        "dxy_trend": macro_result.dxy_trend,
    }
    logger.info(f"  -> Couche 1 : {macro_result.bias}")

    if macro_result.bias == "NEUTRE":
        return FunnelResult(
            passed=False,
            stopped_at_layer=1,
            reason=f"Biais macro NEUTRE (taux={macro_result.dfii10_trend:.4f}, DXY={macro_result.dxy_trend:.4f})",
            layers=layers,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 2 : COT
    # ─────────────────────────────────────────────────────────────────────────
    logger.info(f"[{ts}] Couche 2 — Positionnement COT...")
    try:
        cot_result = cot.get_state(zscore_threshold=cot_zscore_threshold)
    except Exception as e:
        logger.error(f"Erreur layer 2 (COT) : {e}")
        cot_result = cot.COTState(
            state="OK",
            zscore=0.0,
            net_position=0.0,
            details={"error": str(e)},
        )

    layers["cot"] = {
        "state": cot_result.state,
        "zscore": cot_result.zscore,
        "net_position": cot_result.net_position,
    }
    logger.info(f"  -> Couche 2 : {cot_result.state} (z={cot_result.zscore:.2f})")

    # Vérifier si le COT sature le sens du biais
    saturates = (
        (macro_result.bias == "LONG_ONLY" and cot_result.state == "SATURÉ_LONG")
        or (macro_result.bias == "SHORT_ONLY" and cot_result.state == "SATURÉ_SHORT")
    )
    if saturates:
        return FunnelResult(
            passed=False,
            stopped_at_layer=2,
            reason=(
                f"COT sature le biais {macro_result.bias} : "
                f"{cot_result.state} (z-score={cot_result.zscore:.2f})"
            ),
            layers=layers,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 3 : Calendrier
    # ─────────────────────────────────────────────────────────────────────────
    logger.info(f"[{ts}] Couche 3 — Calendrier économique...")
    try:
        cal_result = calendar.check(
            block_hours=calendar_block_hours,
            reduce_hours=calendar_reduce_hours,
        )
    except Exception as e:
        logger.error(f"Erreur layer 3 (calendrier) : {e}")
        cal_result = calendar.CalendarStatus(
            status="TAILLE_RÉDUITE",
            details={"error": str(e)},
        )

    layers["calendar"] = {
        "status": cal_result.status,
        "next_event": cal_result.next_event,
        "hours_until_event": cal_result.hours_until_event,
    }
    logger.info(f"  -> Couche 3 : {cal_result.status}")

    if cal_result.status == "BLOQUÉ":
        event_info = ""
        if cal_result.next_event:
            event_info = f" — '{cal_result.next_event.get('title', '')}' dans {cal_result.hours_until_event:.1f}h"
        return FunnelResult(
            passed=False,
            stopped_at_layer=3,
            reason=f"Calendrier BLOQUÉ{event_info}",
            layers=layers,
        )

    # Réduction de taille si événement proche
    size_reduction = 0.5 if cal_result.status == "TAILLE_RÉDUITE" else 1.0

    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 4 : Signal technique (V3 Trend Rider)
    # ─────────────────────────────────────────────────────────────────────────
    logger.info(f"[{ts}] Couche 4 — Signal technique (bias={macro_result.bias})...")
    try:
        signal = trend_rider.check(df_ohlcv, allowed_bias=macro_result.bias)
    except Exception as e:
        logger.error(f"Erreur layer 4 (trend rider) : {e}")
        signal = TrendSignal(
            direction=None,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            confidence=0.0,
            details={"error": str(e)},
        )

    layers["signal"] = {
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "confidence": signal.confidence,
    }
    logger.info(f"  -> Couche 4 : direction={signal.direction}")

    if signal.direction is None:
        return FunnelResult(
            passed=False,
            stopped_at_layer=4,
            reason=f"Pas de signal technique ({signal.details.get('reason', 'conditions incomplètes')})",
            signal=signal,
            layers=layers,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # SIZING
    # ─────────────────────────────────────────────────────────────────────────
    try:
        sizing = risk.size_position(
            signal=signal,
            capital=capital,
            risk_pct=risk_pct,
            size_reduction=size_reduction,
        )
    except Exception as e:
        logger.error(f"Erreur calcul sizing : {e}")
        sizing = {"units": 0.0, "lots": 0.0, "risk_amount": 0.0, "error": str(e)}

    # Enregistrement dans le log
    trade_proposal = {
        "timestamp": ts,
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "sizing": sizing,
        "layers": layers,
        "size_reduction": size_reduction,
        "calendar_status": cal_result.status,
    }

    try:
        risk.log_trade_proposal(trade_proposal)
    except Exception as e:
        logger.warning(f"Impossible de logger la proposition de trade : {e}")

    logger.info(
        f"TRADE PROPOSÉ : {signal.direction} XAU/USD | "
        f"Entry={signal.entry_price} | SL={signal.stop_loss} | TP={signal.take_profit} | "
        f"Lots={sizing.get('lots', 0):.4f}"
    )

    return FunnelResult(
        passed=True,
        stopped_at_layer=None,
        reason="Toutes les couches passées — trade proposé",
        signal=signal,
        trade_proposal=trade_proposal,
        layers=layers,
    )
