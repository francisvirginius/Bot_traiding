"""
Module pour charger la configuration
"""
import yaml
import os
from dotenv import load_dotenv
from typing import Dict


class ConfigLoader:
    """Charge la configuration depuis les fichiers"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        load_dotenv()

    def load(self) -> Dict:
        """Charge la configuration depuis le fichier YAML"""
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Remplace les variables d'environnement si présentes
        if 'telegram' in config:
            config['telegram']['bot_token'] = os.getenv(
                'TELEGRAM_BOT_TOKEN',
                config['telegram'].get('bot_token', '')
            )
            config['telegram']['chat_id'] = os.getenv(
                'TELEGRAM_CHAT_ID',
                config['telegram'].get('chat_id', '')
            )

        if 'email' in config:
            config['email']['sender_password'] = os.getenv(
                'EMAIL_PASSWORD',
                config['email'].get('sender_password', '')
            )

        # Ajoute les clés API Binance
        config['binance'] = {
            'api_key': os.getenv('BINANCE_API_KEY'),
            'api_secret': os.getenv('BINANCE_API_SECRET')
        }

        # Ajoute la clé API Twelve Data
        if 'twelvedata' in config:
            config['twelvedata']['api_key'] = os.getenv(
                'TWELVEDATA_API_KEY',
                config['twelvedata'].get('api_key', '')
            )

        return config
