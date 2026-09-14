"""
V3 Trend Rider — Génère un signal d'entrée en combinant indicateurs et structure.

Signal LONG si :
  1. EMA50 > EMA200
  2. MACD line > signal line
  3. ADX > 20
  4. Prix proche d'une zone demand (dans les 0.5%)
  5. Dernier BOS = BULLISH

Signal SHORT si :
  1. EMA50 < EMA200
  2. MACD line < signal line
  3. ADX > 20
  4. Prix proche d'une zone supply (dans les 0.5%)
  5. Dernier BOS = BEARISH
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from gold_bot.strategy.indicators import compute_indicators
from gold_bot.strategy.structure import analyze_structure

logger = logging.getLogger(__name__)

ADX_THRESHOLD = 20
ZONE_PROXIMITY_PCT = 0.005   # 0.5%
MIN_RR = 2.5                 # R:R minimum


@dataclass
class TrendSignal:
    direction: Optional[str]       # 'LONG' | 'SHORT' | None
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float              # 0.0 à 1.0 (nb conditions remplies / total)
    details: dict = field(default_factory=dict)


def _nearest_zone(price: float, zones: list, proximity_pct: float = ZONE_PROXIMITY_PCT) -> Optional[dict]:
    """Retourne la zone la plus proche si elle est dans la proximité définie, sinon None."""
    best = None
    best_dist = float("inf")
    for zone in zones:
        dist = abs(price - zone["price_center"]) / price
        if dist <= proximity_pct and dist < best_dist:
            best = zone
            best_dist = dist
    return best


def _compute_stop_long(structure: dict, current_price: float) -> float:
    """Stop-loss pour un LONG : sous le dernier swing low valide."""
    swing_lows = structure.get("swing_lows", [])
    if not swing_lows:
        # Fallback : 1.5% sous le prix
        return round(current_price * 0.985, 2)
    # Dernier swing low
    last_low = swing_lows[-1]["price"]
    # Buffer de 0.1% sous le swing low
    return round(last_low * 0.999, 2)


def _compute_stop_short(structure: dict, current_price: float) -> float:
    """Stop-loss pour un SHORT : au-dessus du dernier swing high valide."""
    swing_highs = structure.get("swing_highs", [])
    if not swing_highs:
        # Fallback : 1.5% au-dessus du prix
        return round(current_price * 1.015, 2)
    last_high = swing_highs[-1]["price"]
    return round(last_high * 1.001, 2)


def _compute_take_profit(entry: float, stop: float, rr: float = MIN_RR) -> float:
    """Calcule le TP en fonction du R:R minimum."""
    risk = abs(entry - stop)
    if entry > stop:  # LONG
        return round(entry + risk * rr, 2)
    else:  # SHORT
        return round(entry - risk * rr, 2)


def check(
    df: pd.DataFrame,
    allowed_bias: str = "NEUTRE",
    adx_threshold: float = ADX_THRESHOLD,
    zone_proximity_pct: float = ZONE_PROXIMITY_PCT,
    min_rr: float = MIN_RR,
) -> TrendSignal:
    """
    Analyse le DataFrame OHLCV et génère un signal de trading.

    Args:
        df: DataFrame OHLCV (minimum ~250 bougies recommandé)
        allowed_bias: 'LONG_ONLY' | 'SHORT_ONLY' | 'NEUTRE'
        adx_threshold: Seuil ADX pour confirmer la tendance
        zone_proximity_pct: Proximité en % aux zones S/D
        min_rr: R:R minimum pour le TP

    Returns:
        TrendSignal dataclass (direction=None si pas de signal)
    """
    no_signal = TrendSignal(
        direction=None,
        entry_price=0.0,
        stop_loss=0.0,
        take_profit=0.0,
        confidence=0.0,
        details={"reason": "aucune condition remplie"},
    )

    if df is None or df.empty:
        logger.warning("DataFrame vide passé à trend_rider.check()")
        return no_signal

    if len(df) < 30:
        logger.warning(f"DataFrame trop court : {len(df)} bougies (minimum 30 recommandé)")
        no_signal.details["reason"] = "données insuffisantes"
        return no_signal

    # Calcul des indicateurs
    try:
        df_ind = compute_indicators(df)
    except Exception as e:
        logger.error(f"Erreur calcul indicateurs : {e}")
        no_signal.details["reason"] = f"erreur indicateurs: {e}"
        return no_signal

    # Analyse de la structure
    try:
        structure = analyze_structure(df_ind)
    except Exception as e:
        logger.error(f"Erreur analyse structure : {e}")
        no_signal.details["reason"] = f"erreur structure: {e}"
        return no_signal

    # Valeurs courantes (dernière bougie)
    last = df_ind.iloc[-1]
    current_price = float(last["close"])

    ema50 = last.get("ema50", float("nan"))
    ema200 = last.get("ema200", float("nan"))
    macd_line = last.get("macd", float("nan"))
    macd_sig = last.get("macd_signal", float("nan"))
    adx_val = last.get("adx", float("nan"))
    last_bos = structure.get("last_bos")

    import math
    if any(math.isnan(v) for v in [ema50, ema200, macd_line, macd_sig, adx_val]):
        logger.warning("Valeurs NaN dans les indicateurs (données insuffisantes pour la période ?)")
        no_signal.details["reason"] = "indicateurs NaN — données insuffisantes"
        return no_signal

    supply_zones = structure.get("supply_zones", [])
    demand_zones = structure.get("demand_zones", [])

    # ─── Test LONG ────────────────────────────────────────────────────────────
    long_conditions = {
        "ema_uptrend": ema50 > ema200,
        "macd_bullish": macd_line > macd_sig,
        "adx_strong": adx_val > adx_threshold,
        "near_demand": _nearest_zone(current_price, demand_zones, zone_proximity_pct) is not None,
        "bos_bullish": last_bos == "BULLISH",
    }
    long_score = sum(long_conditions.values()) / len(long_conditions)

    # ─── Test SHORT ───────────────────────────────────────────────────────────
    short_conditions = {
        "ema_downtrend": ema50 < ema200,
        "macd_bearish": macd_line < macd_sig,
        "adx_strong": adx_val > adx_threshold,
        "near_supply": _nearest_zone(current_price, supply_zones, zone_proximity_pct) is not None,
        "bos_bearish": last_bos == "BEARISH",
    }
    short_score = sum(short_conditions.values()) / len(short_conditions)

    # ─── Décision ─────────────────────────────────────────────────────────────
    direction = None
    all_conditions = {}

    long_valid = all(long_conditions.values()) and allowed_bias in ("LONG_ONLY", "NEUTRE")
    short_valid = all(short_conditions.values()) and allowed_bias in ("SHORT_ONLY", "NEUTRE")

    if long_valid and (not short_valid or long_score >= short_score):
        direction = "LONG"
        all_conditions = long_conditions
        confidence = long_score
    elif short_valid:
        direction = "SHORT"
        all_conditions = short_conditions
        confidence = short_score
    else:
        # Aucun signal complet — log les conditions partielles
        logger.info(
            f"Trend Rider : pas de signal | "
            f"LONG={long_score*100:.0f}% ({sum(long_conditions.values())}/5) | "
            f"SHORT={short_score*100:.0f}% ({sum(short_conditions.values())}/5) | "
            f"bias={allowed_bias}"
        )
        return TrendSignal(
            direction=None,
            entry_price=current_price,
            stop_loss=0.0,
            take_profit=0.0,
            confidence=max(long_score, short_score),
            details={
                "reason": "conditions incomplètes",
                "allowed_bias": allowed_bias,
                "long_conditions": long_conditions,
                "short_conditions": short_conditions,
                "adx": round(adx_val, 2),
                "ema50": round(ema50, 2),
                "ema200": round(ema200, 2),
                "last_bos": last_bos,
            },
        )

    # ─── Calcul SL / TP ───────────────────────────────────────────────────────
    entry_price = current_price
    if direction == "LONG":
        stop_loss = _compute_stop_long(structure, entry_price)
    else:
        stop_loss = _compute_stop_short(structure, entry_price)

    take_profit = _compute_take_profit(entry_price, stop_loss, min_rr)

    # Vérification cohérence
    if direction == "LONG" and (stop_loss >= entry_price or take_profit <= entry_price):
        logger.warning(f"SL/TP incohérents pour LONG : entry={entry_price}, SL={stop_loss}, TP={take_profit}")
        no_signal.details["reason"] = "SL/TP incohérents (LONG)"
        return no_signal

    if direction == "SHORT" and (stop_loss <= entry_price or take_profit >= entry_price):
        logger.warning(f"SL/TP incohérents pour SHORT : entry={entry_price}, SL={stop_loss}, TP={take_profit}")
        no_signal.details["reason"] = "SL/TP incohérents (SHORT)"
        return no_signal

    rr_actual = abs(take_profit - entry_price) / abs(entry_price - stop_loss)

    logger.info(
        f"SIGNAL {direction} | Entry={entry_price:.2f} | SL={stop_loss:.2f} | "
        f"TP={take_profit:.2f} | R:R={rr_actual:.2f} | confidence={confidence:.0%}"
    )

    return TrendSignal(
        direction=direction,
        entry_price=round(entry_price, 2),
        stop_loss=round(stop_loss, 2),
        take_profit=round(take_profit, 2),
        confidence=round(confidence, 4),
        details={
            "allowed_bias": allowed_bias,
            "conditions": all_conditions,
            "adx": round(adx_val, 2),
            "ema50": round(ema50, 2),
            "ema200": round(ema200, 2),
            "macd": round(macd_line, 4),
            "macd_signal": round(macd_sig, 4),
            "last_bos": last_bos,
            "rr": round(rr_actual, 2),
            "swing_highs_count": len(structure.get("swing_highs", [])),
            "swing_lows_count": len(structure.get("swing_lows", [])),
        },
    )
