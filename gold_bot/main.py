"""
Gold Bot — Orchestration principale
Robot de trading XAU/USD en 4 couches (entonnoir).
Le robot PROPOSE des trades, il n'exécute aucun ordre automatiquement.

Usage :
    python -m gold_bot.main           # Exécution unique
    python -m gold_bot.main --loop    # Mode boucle (toutes les heures)
    python -m gold_bot.main --mock    # Données mockées (test sans API)
"""
import io
import os
import sys
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Encodage UTF-8 pour la console Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ajouter le répertoire racine au path Python
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path(__file__).parent / "logs" / "gold_bot.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("gold_bot.main")


def load_config() -> dict:
    """Charge la configuration depuis config.yaml."""
    try:
        import yaml
        config_path = ROOT_DIR / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        gold_cfg = config.get("gold_bot", {})
        logger.info(f"Configuration chargée depuis {config_path}")
        return config, gold_cfg
    except Exception as e:
        logger.warning(f"Impossible de lire config.yaml : {e} — utilisation des defaults")
        return {}, {}


def get_ohlcv_data(config: dict, timeframe: str = "1h", outputsize: int = 300) -> Optional[object]:
    """
    Récupère les données OHLCV XAU/USD via TwelveData.
    Retourne None en cas d'échec.
    """
    try:
        from src.twelve_data_fetcher import TwelveDataFetcher
        td_cfg = config.get("twelvedata", {})
        api_key = td_cfg.get("api_key", "") or os.environ.get("TWELVEDATA_API_KEY", "")
        fetcher = TwelveDataFetcher(api_key=api_key)
        df = fetcher.get_historical_data("XAU/USD", timeframe, outputsize=outputsize)
        logger.info(f"OHLCV XAU/USD : {len(df)} bougies ({timeframe}) récupérées")
        return df
    except Exception as e:
        logger.error(f"Erreur récupération données OHLCV : {e}")
        return None


def get_mock_ohlcv(n: int = 300) -> object:
    """Génère des données OHLCV mockées pour les tests sans API."""
    import numpy as np
    import pandas as pd

    logger.warning("Mode MOCK : données OHLCV générées artificiellement")
    np.random.seed(42)

    base_price = 2300.0
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=n, freq="1h")
    returns = np.random.normal(0, 0.002, n)  # 0.2% de volatilité horaire
    closes = base_price * np.exp(np.cumsum(returns))

    # Simuler une tendance haussière légère (favorable aux signaux LONG)
    trend = np.linspace(0, 50, n)
    closes = closes + trend

    highs = closes * (1 + np.abs(np.random.normal(0, 0.001, n)))
    lows = closes * (1 - np.abs(np.random.normal(0, 0.001, n)))
    opens = np.roll(closes, 1)
    opens[0] = closes[0]

    df = pd.DataFrame({
        "timestamp": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.random.randint(1000, 5000, n).astype(float),
    })
    return df


def send_telegram_notification(config: dict, message: str) -> None:
    """Envoie une notification Telegram si configuré."""
    try:
        from src.notifiers import TelegramNotifier
        tg_cfg = config.get("telegram", {})
        bot_token = tg_cfg.get("bot_token", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = tg_cfg.get("chat_id", "") or os.environ.get("TELEGRAM_CHAT_ID", "")

        if not bot_token or bot_token == "YOUR_BOT_TOKEN":
            logger.info("Telegram non configuré — notification ignorée")
            return

        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Notification Telegram envoyée")
    except Exception as e:
        logger.warning(f"Erreur envoi Telegram : {e}")


def format_trade_proposal(result, capital: float, risk_pct: float) -> str:
    """Formate la proposition de trade pour l'affichage console et Telegram."""
    signal = result.signal
    layers = result.layers
    proposal = result.trade_proposal or {}
    sizing = proposal.get("sizing", {})

    entry = signal.entry_price
    sl = signal.stop_loss
    tp = signal.take_profit
    direction = signal.direction

    # Calcul des pourcentages
    sl_pct = (sl - entry) / entry * 100
    tp_pct = (tp - entry) / entry * 100
    rr = abs(tp - entry) / abs(entry - sl) if entry != sl else 0

    lots = sizing.get("lots", 0)
    risk_display_pct = risk_pct * 100
    size_reduction = proposal.get("size_reduction", 1.0)
    if size_reduction < 1.0:
        risk_display_pct *= size_reduction

    cal_status = proposal.get("calendar_status", "TRADE_OK")
    macro_bias = layers.get("macro", {}).get("bias", "?")
    cot_state = layers.get("cot", {}).get("state", "?")
    sig_direction = layers.get("signal", {}).get("direction", "?")

    # Symboles de check
    ck = "OK"

    lines = [
        "═══════════════════════════════════════════",
        "  PROPOSITION DE TRADE — XAU/USD",
        "═══════════════════════════════════════════",
        f"  Direction   : {direction}",
        f"  Entree      : {entry:,.2f}",
        f"  Stop-Loss   : {sl:,.2f}  ({sl_pct:+.2f}%)",
        f"  Take-Profit : {tp:,.2f}  ({tp_pct:+.2f}%)  R:R = {rr:.1f}",
        f"  Taille      : {lots:.2f} lots (risque : {risk_display_pct:.1f}% capital)",
        "",
        f"  Couche 1 (Macro)       : {macro_bias}  [{ck}]",
        f"  Couche 2 (COT)         : {cot_state}  [{ck}]",
        f"  Couche 3 (Calendrier)  : {cal_status}  [{ck}]",
        f"  Couche 4 (Technique)   : SIGNAL {sig_direction}  [{ck}]",
        "",
        "  *** VALIDATION HUMAINE REQUISE ***",
        "═══════════════════════════════════════════",
    ]
    return "\n".join(lines)


def save_report(output: str, timestamp: str) -> None:
    """Sauvegarde le rapport dans gold_bot/logs/rapports.txt (append)."""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    report_path = log_dir / "rapports.txt"
    with open(report_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{timestamp}]\n")
        f.write(output)
        f.write("\n")
    logger.info(f"Rapport sauvegardé dans {report_path}")


def format_no_trade(result) -> str:
    """Formate le résumé quand aucun trade n'est proposé."""
    layer_names = {
        1: "Macro",
        2: "COT",
        3: "Calendrier",
        4: "Technique",
    }
    layer_name = layer_names.get(result.stopped_at_layer, "?") if result.stopped_at_layer else "?"

    lines = [
        "─────────────────────────────────────────",
        "  PAS DE TRADE — XAU/USD",
        "─────────────────────────────────────────",
        f"  Bloqué à la couche {result.stopped_at_layer} ({layer_name})",
        f"  Raison : {result.reason}",
        "─────────────────────────────────────────",
    ]
    return "\n".join(lines)


def run_once(config: dict, gold_cfg: dict, mock: bool = False) -> None:
    """Exécute le funnel une seule fois."""
    from gold_bot.engine import funnel

    capital = gold_cfg.get("capital", 10_000)
    risk_pct = gold_cfg.get("risk_pct", 0.01)
    timeframe = gold_cfg.get("timeframe", "1h")
    cot_threshold = gold_cfg.get("cot_zscore_threshold", 1.5)
    block_hours = gold_cfg.get("calendar_block_hours", 4)
    reduce_hours = gold_cfg.get("calendar_reduce_hours", 24)

    fred_api_key = os.environ.get("FRED_API_KEY", "")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n[{ts}] Analyse XAU/USD en cours...")

    # Récupération des données OHLCV
    if mock:
        df = get_mock_ohlcv(n=300)
    else:
        df = get_ohlcv_data(config, timeframe=timeframe, outputsize=300)
        if df is None:
            logger.error("Impossible de récupérer les données OHLCV — arrêt")
            print("ERREUR : Données OHLCV non disponibles. Utilisez --mock pour les tests.")
            return

    # Exécution du funnel
    result = funnel.run(
        df_ohlcv=df,
        capital=capital,
        risk_pct=risk_pct,
        fred_api_key=fred_api_key if fred_api_key else None,
        cot_zscore_threshold=cot_threshold,
        calendar_block_hours=block_hours,
        calendar_reduce_hours=reduce_hours,
    )

    # Affichage du résultat
    if result.passed and result.signal and result.signal.direction:
        output = format_trade_proposal(result, capital, risk_pct)
        print("\n" + output)
        save_report(output, ts)
        # Notification Telegram
        send_telegram_notification(config, output.replace("═", "=").replace("─", "-"))
    else:
        output = format_no_trade(result)
        print("\n" + output)
        save_report(output, ts)

    return result


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Gold Bot — Robot de proposition de trades XAU/USD"
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Mode boucle (vérifie toutes les heures)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Utilise des données mockées (test sans API)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Intervalle de vérification en secondes (override config)",
    )
    args = parser.parse_args()

    # Création des dossiers nécessaires
    (Path(__file__).parent / "logs").mkdir(parents=True, exist_ok=True)
    (Path(__file__).parent / "cache").mkdir(parents=True, exist_ok=True)

    config, gold_cfg = load_config()

    check_interval = args.interval or gold_cfg.get("check_interval", 3600)

    print("╔══════════════════════════════════════════╗")
    print("║         GOLD BOT — XAU/USD v1.0          ║")
    print("║   Système de proposition de trades 4C    ║")
    print("╚══════════════════════════════════════════╝")

    if args.mock:
        print("  [MODE MOCK — données artificielles]")

    if args.loop:
        print(f"  Mode boucle : vérification toutes les {check_interval}s")
        print("  Appuyez sur Ctrl+C pour arrêter\n")
        while True:
            try:
                run_once(config, gold_cfg, mock=args.mock)
                print(f"\nProchaine vérification dans {check_interval}s...")
                time.sleep(check_interval)
            except KeyboardInterrupt:
                print("\n\nArrêt du Gold Bot.")
                break
            except Exception as e:
                logger.error(f"Erreur inattendue dans la boucle : {e}", exc_info=True)
                print(f"Erreur : {e} — reprise dans {check_interval}s...")
                time.sleep(check_interval)
    else:
        run_once(config, gold_cfg, mock=args.mock)


if __name__ == "__main__":
    main()
