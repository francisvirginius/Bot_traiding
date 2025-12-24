# AlerteTrade - Système d'alertes Bollinger Bands

Système d'alerte intelligent qui te prévient **AVANT** que le prix touche les bandes de Bollinger, pour que tu sois déjà prêt quand l'élastique commence à se tendre.

## 🎯 Philosophie

Ce projet suit la logique d'un trader pro :

> "Le marché est très étiré → je me mets en position → j'attends que le prix me prouve s'il revient ou continue"

Tu n'essaies pas de prédire, tu te prépares quand les conditions sont favorables.

## ✨ Fonctionnalités

- Calcul automatique des Bandes de Bollinger
- Alertes de proximité configurables (par défaut 0.1%)
- Anti-spam : cooldown de 5 minutes entre alertes similaires
- Notifications multiples : Console, Telegram, Email
- Historique des alertes sauvegardé
- Configuration simple via YAML

## 📦 Installation

### 1. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 2. Configuration

Copie le fichier d'exemple et configure tes paramètres :

```bash
cp .env.example .env
```

Édite [config.yaml](config.yaml) pour ajuster :
- La paire à surveiller (défaut: BTCUSDT)
- L'intervalle (1m, 5m, 15m, 1h, 4h, 1d)
- Les paramètres des Bandes de Bollinger
- Le seuil de proximité (0.1% = très proche)
- Les méthodes de notification

### 3. Configuration Binance (optionnel)

Pour récupérer les données en temps réel, crée des clés API sur Binance :
1. Va sur Binance → Profil → API Management
2. Crée une clé API (permissions de lecture uniquement)
3. Ajoute les clés dans [.env](.env)

**Note**: Les clés API ne sont PAS obligatoires pour les données publiques.

### 4. Configuration Telegram (optionnel)

Pour recevoir des alertes Telegram :

1. Crée un bot via [@BotFather](https://t.me/botfather)
2. Récupère ton Chat ID via [@userinfobot](https://t.me/userinfobot)
3. Ajoute les infos dans [.env](.env)
4. Active Telegram dans [config.yaml](config.yaml)

## 🚀 Utilisation

### Lancement simple

```bash
python main.py
```

### Ce que tu verras

```
🚀 Démarrage du système d'alerte Bollinger Bands
============================================================
✅ Configuration chargée
📊 Symbole: BTCUSDT
⏱️  Intervalle: 1h
🔄 Vérification toutes les 60s
📏 Proximité: 0.1%
============================================================

✅ Système initialisé et en fonctionnement

[14:23:45] Prix: 43250.00 | Haute: 43500.00 (0.574%) | Basse: 42800.00 (1.051%)
[14:24:45] Prix: 43480.00 | Haute: 43500.00 (0.046%) | Basse: 42800.00 (1.588%)

============================================================
⚠️ ALERTE BANDE HAUTE
Timestamp: 2024-01-15T14:24:45.123456
Prix actuel: 43480.0
Bande upper: 43500.0
Distance: 0.046%
============================================================
```

## 📊 Structure du projet

```
AlerteTrade/
├── main.py                    # Script principal
├── config.yaml                # Configuration
├── requirements.txt           # Dépendances
├── .env.example              # Template variables d'environnement
├── README.md                 # Ce fichier
└── src/
    ├── bollinger_bands.py    # Calcul des BB et proximité
    ├── data_fetcher.py       # Récupération des données Binance
    ├── alert_manager.py      # Gestion des alertes et anti-spam
    ├── notifiers.py          # Système de notifications
    └── config_loader.py      # Chargement de la config
```

## ⚙️ Configuration avancée

### Ajuster la sensibilité

Dans [config.yaml](config.yaml) :

```yaml
bollinger_bands:
  proximity_percent: 0.1    # Plus petit = alerte plus tôt
```

- `0.05%` : Très proche, alerte quasi au contact
- `0.1%` : Recommandé pour la plupart des marchés
- `0.5%` : Plus large, alerte anticipée

### Modifier les paramètres BB

```yaml
bollinger_bands:
  period: 20          # Standard : 20
  multiplier: 2.0     # Standard : 2
```

### Cooldown entre alertes

Dans [src/alert_manager.py](src/alert_manager.py:17) :

```python
self.cooldown_seconds = 300  # 5 minutes par défaut
```

## 🔧 Évolutions possibles

- [ ] Support d'autres exchanges (Bybit, OKX, etc.)
- [ ] Dashboard web en temps réel
- [ ] Backtesting sur données historiques
- [ ] Alertes Discord/Slack
- [ ] Multi-symboles simultanés
- [ ] Stratégies de trading automatiques

## 🛡️ Sécurité

- Ne partage JAMAIS tes clés API
- Utilise des clés avec permissions de lecture uniquement
- Ajoute [.env](.env) dans [.gitignore](.gitignore) (déjà fait)

## 📝 Notes

- Le système affiche les infos en temps réel toutes les 60 secondes
- L'historique est sauvegardé automatiquement à l'arrêt (Ctrl+C)
- Les alertes sont espacées de 5 minutes pour éviter le spam

## 🐛 Résolution de problèmes

### Erreur "API key not found"
→ Les clés API ne sont pas obligatoires pour les données publiques

### Erreur "Module not found"
→ Vérifie que tu as installé les dépendances : `pip install -r requirements.txt`

### Pas de notification Telegram
→ Vérifie que bot_token et chat_id sont corrects dans [.env](.env)

## 📞 Support

Pour toute question ou amélioration, ouvre une issue ou modifie directement le code !

---

**Bon trading ! 🚀**
