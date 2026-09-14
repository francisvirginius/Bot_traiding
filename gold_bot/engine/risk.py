"""
Gestion du risque :
  - size_position : calcule la taille de position (units et lots)
  - log_expectancy : calcule l'espérance mathématique sur l'historique des trades
  - log_trade_proposal : persiste les propositions dans trade_log.json
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).parent.parent / "logs"
TRADE_LOG_FILE = LOG_DIR / "trade_log.json"

# 1 lot standard XAU/USD = 100 oz
# Pour les unités en oz (ou contrats), on exprime en lots (divisé par 100)
OZ_PER_LOT = 100.0


def size_position(
    signal,
    capital: float,
    risk_pct: float = 0.01,
    size_reduction: float = 1.0,
) -> dict:
    """
    Calcule la taille de position en fonction du risque.

    Formule :
        pip_risk = |entry_price - stop_loss|
        risk_amount = capital * risk_pct * size_reduction
        units = risk_amount / pip_risk  (en oz pour XAU/USD)
        lots = units / 100

    Args:
        signal: TrendSignal (doit avoir entry_price et stop_loss)
        capital: Capital total en USD
        risk_pct: Fraction du capital risquée par trade (0.01 = 1%)
        size_reduction: Facteur de réduction (0.5 si TAILLE_RÉDUITE, 1.0 sinon)

    Returns:
        dict avec : units, lots, risk_amount, pip_risk, effective_risk_pct
    """
    entry = float(signal.entry_price)
    sl = float(signal.stop_loss)

    pip_risk = abs(entry - sl)
    if pip_risk == 0:
        logger.error("pip_risk = 0 — stop-loss identique à l'entrée, sizing impossible")
        return {
            "units": 0.0,
            "lots": 0.0,
            "risk_amount": 0.0,
            "pip_risk": 0.0,
            "effective_risk_pct": 0.0,
            "size_reduction": size_reduction,
            "error": "pip_risk=0",
        }

    risk_amount = capital * risk_pct * size_reduction
    units = risk_amount / pip_risk
    lots = units / OZ_PER_LOT

    # Arrondi à 2 décimales pour les lots
    lots_rounded = round(lots, 2)
    units_rounded = lots_rounded * OZ_PER_LOT

    effective_risk = (units_rounded * pip_risk) / capital if capital > 0 else 0.0

    logger.info(
        f"Sizing : capital={capital:,.0f} USD | risque={risk_pct*100:.1f}% "
        f"x{size_reduction} | pip_risk={pip_risk:.2f} | "
        f"units={units_rounded:.1f} oz | lots={lots_rounded:.2f} | "
        f"risque_effectif={effective_risk*100:.2f}%"
    )

    return {
        "units": round(units_rounded, 4),
        "lots": lots_rounded,
        "risk_amount": round(risk_amount, 2),
        "pip_risk": round(pip_risk, 4),
        "effective_risk_pct": round(effective_risk, 6),
        "size_reduction": size_reduction,
    }


def log_expectancy(trade_results: list) -> dict:
    """
    Calcule et affiche l'espérance mathématique sur une liste de trades.

    Format attendu pour chaque trade :
        {"pnl": float, "won": bool}  ou  {"result": float}

    Formule : E = (win_rate * avg_win) - (loss_rate * avg_loss)

    Returns:
        dict avec : expectancy, win_rate, avg_win, avg_loss, nb_trades
    """
    if not trade_results:
        logger.warning("Aucun résultat de trade pour calculer l'espérance")
        return {"expectancy": 0.0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "nb_trades": 0}

    wins = []
    losses = []

    for t in trade_results:
        # Supporte deux formats
        if "pnl" in t:
            pnl = float(t["pnl"])
        elif "result" in t:
            pnl = float(t["result"])
        else:
            continue

        if pnl > 0:
            wins.append(pnl)
        else:
            losses.append(abs(pnl))

    nb_trades = len(wins) + len(losses)
    if nb_trades == 0:
        return {"expectancy": 0.0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "nb_trades": 0}

    win_rate = len(wins) / nb_trades
    loss_rate = 1.0 - win_rate
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0

    expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

    logger.info(
        f"Esperance : E={expectancy:.2f} USD | "
        f"win_rate={win_rate*100:.1f}% | avg_win={avg_win:.2f} | avg_loss={avg_loss:.2f} | "
        f"nb_trades={nb_trades}"
    )

    if expectancy < 0:
        logger.warning(
            f"ALERTE : Esperance NEGATIVE ({expectancy:.2f} USD) sur {nb_trades} trades — "
            "revoir la stratégie !"
        )

    result = {
        "expectancy": round(expectancy, 4),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "nb_trades": nb_trades,
        "nb_wins": len(wins),
        "nb_losses": len(losses),
    }

    print(f"\n{'='*50}")
    print(f"  ESPERANCE MATHEMATIQUE")
    print(f"{'='*50}")
    print(f"  Nb trades     : {nb_trades}")
    print(f"  Win rate      : {win_rate*100:.1f}%")
    print(f"  Gain moyen    : +{avg_win:.2f} USD")
    print(f"  Perte moyenne : -{avg_loss:.2f} USD")
    print(f"  Esperance     : {expectancy:+.2f} USD par trade")
    if expectancy < 0:
        print(f"  *** ALERTE : Esperance negative ! ***")
    print(f"{'='*50}\n")

    return result


def log_trade_proposal(proposal: dict) -> None:
    """
    Persiste une proposition de trade dans trade_log.json (append).

    Le fichier est un JSON array de propositions.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Lire l'existant
    existing = []
    if TRADE_LOG_FILE.exists():
        try:
            with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if not isinstance(existing, list):
                existing = []
        except (json.JSONDecodeError, IOError):
            existing = []

    # Ajouter la nouvelle proposition
    entry = {
        **proposal,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    existing.append(entry)

    # Réécrire
    try:
        with open(TRADE_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False, default=str)
        logger.debug(f"Proposition loguée dans {TRADE_LOG_FILE}")
    except IOError as e:
        logger.error(f"Impossible d'écrire dans {TRADE_LOG_FILE} : {e}")


def load_trade_history() -> list:
    """Charge l'historique des trades depuis trade_log.json."""
    if not TRADE_LOG_FILE.exists():
        return []
    try:
        with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Impossible de lire l'historique des trades : {e}")
        return []
