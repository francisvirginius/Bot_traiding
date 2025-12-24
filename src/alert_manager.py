"""
Module de gestion des alertes
"""
from datetime import datetime
from typing import Dict, List
import json


class AlertManager:
    """Gère la détection et l'historique des alertes"""

    def __init__(self):
        self.last_alert_upper = None
        self.last_alert_lower = None
        self.cooldown_seconds = 300  # 5 minutes entre alertes similaires
        self.alert_history = []

    def should_alert(self, alert_type: str) -> bool:
        """
        Vérifie si on doit déclencher une alerte (évite le spam)

        Args:
            alert_type: 'upper' ou 'lower'

        Returns:
            True si on peut alerter
        """
        now = datetime.now()
        last_alert = self.last_alert_upper if alert_type == 'upper' else self.last_alert_lower

        if last_alert is None:
            return True

        time_since_last = (now - last_alert).total_seconds()
        return time_since_last >= self.cooldown_seconds

    def trigger_alert(self, alert_type: str, proximity_data: Dict) -> Dict:
        """
        Déclenche une alerte

        Args:
            alert_type: 'upper' ou 'lower'
            proximity_data: Données de proximité

        Returns:
            Dict avec les informations de l'alerte
        """
        now = datetime.now()

        if alert_type == 'upper':
            self.last_alert_upper = now
            message = f"⚠️ ALERTE BANDE HAUTE"
            band_value = proximity_data['upper_band']
            distance = proximity_data['distance_upper_pct']
        else:
            self.last_alert_lower = now
            message = f"⚠️ ALERTE BANDE BASSE"
            band_value = proximity_data['lower_band']
            distance = proximity_data['distance_lower_pct']

        alert = {
            'timestamp': now.isoformat(),
            'type': alert_type,
            'message': message,
            'price': proximity_data['current_price'],
            'band_value': band_value,
            'distance_pct': distance,
            'details': proximity_data
        }

        self.alert_history.append(alert)
        return alert

    def check_and_alert(self, proximity_data: Dict) -> List[Dict]:
        """
        Vérifie les conditions et déclenche les alertes si nécessaire

        Args:
            proximity_data: Données de proximité des bandes

        Returns:
            Liste des alertes déclenchées
        """
        alerts = []

        # Alerte bande haute
        if proximity_data['near_upper'] and self.should_alert('upper'):
            alert = self.trigger_alert('upper', proximity_data)
            alerts.append(alert)

        # Alerte bande basse
        if proximity_data['near_lower'] and self.should_alert('lower'):
            alert = self.trigger_alert('lower', proximity_data)
            alerts.append(alert)

        return alerts

    def get_alert_history(self, limit: int = 10) -> List[Dict]:
        """
        Récupère l'historique des alertes

        Args:
            limit: Nombre d'alertes à retourner

        Returns:
            Liste des dernières alertes
        """
        return self.alert_history[-limit:]

    def save_history(self, filepath: str):
        """Sauvegarde l'historique dans un fichier"""
        with open(filepath, 'w') as f:
            json.dump(self.alert_history, f, indent=2)

    def load_history(self, filepath: str):
        """Charge l'historique depuis un fichier"""
        try:
            with open(filepath, 'r') as f:
                self.alert_history = json.load(f)
        except FileNotFoundError:
            self.alert_history = []
