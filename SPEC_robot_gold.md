# Spécification — Robot de trading Gold (XAU/USD)

> **Philosophie en une phrase**
> Les couches 1-2-3 disent **oui / non / prudence**, la couche 4 dit **maintenant**, et la gestion du risque dit **combien**.
> La macro ne choisit pas la seconde exacte du clic — elle dit si le vent souffle dans le dos ou de face.

---

## 1. Objectif

Filtrer les trades gold à travers un **entonnoir en 4 couches**, du plus global au plus précis. Un trade ne se déclenche que s'il **survit aux 4 couches**. Le but n'est pas d'avoir raison souvent, mais de garder une **espérance de gain positive** en éliminant les trades à faible probabilité.

Actif : **XAU/USD (gold)** — CFD sur Capital.com.
Style : **trend-following** (swing / position), pas d'intraday agressif.

---

## 2. Les 4 couches (l'entonnoir)

| Couche | Rôle | Source de données | Sortie |
|--------|------|-------------------|--------|
| 1. Macro | Direction globale (biais) | Taux réels `DFII10` (FRED) + DXY | LONG_ONLY / SHORT_ONLY / NEUTRE |
| 2. Positionnement | Le marché est-il saturé ? | COT hebdo — Managed Money | OK / SATURÉ_LONG / SATURÉ_SHORT |
| 3. Calendrier | Ai-je le droit de trader ? | Calendrier éco (CPI, NFP, FOMC, PCE) | TRADE_OK / BLOQUÉ / TAILLE_RÉDUITE |
| 4. Technique | Point d'entrée exact | V3 Trend Rider (EMA/MACD/ADX + supply/demand) | SIGNAL_ENTRÉE ou rien |

### Couche 1 — Biais macro
- **Données** : rendement TIPS 10 ans (`DFII10` sur FRED) + indice dollar (DXY).
- **Règle** :
  - Taux réels en baisse **et** dollar faible → `LONG_ONLY`
  - Taux réels en hausse **et** dollar fort → `SHORT_ONLY` (ou "pas de long")
  - Signaux mixtes → `NEUTRE` (biais prudent)
- **Ne déclenche jamais un trade.** Elle définit seulement le **sens autorisé**.
- Fréquence de mise à jour : quotidienne.

### Couche 2 — Positionnement (COT)
- **Données** : rapport CFTC *Disaggregated*, catégorie **Managed Money** (hedge funds / CTA).
- **Normalisation obligatoire** : z-score ou COT Index sur **3 ans (156 semaines)**. Ne jamais lire les chiffres bruts.
- **Règle** :
  - Managed Money à un extrême **long** historique (z-score haut) → `SATURÉ_LONG` → bloquer / dégrader les signaux d'**achat**
  - Extrême **short** historique → `SATURÉ_SHORT` → bloquer / dégrader les signaux de **vente**
- **Rappel** : donnée publiée vendredi 15h30 (heure NY) sur les positions du **mardi** précédent → décalage de 3 jours. C'est de la **structure/risque**, pas du timing.
- Fréquence : hebdomadaire (mise à jour le vendredi).

### Couche 3 — Calendrier économique
- **Données** : dates + heures des events à fort impact (CPI, NFP, FOMC, PCE, discours Powell).
- **Règle** :
  - Event majeur dans les prochaines N heures → `BLOQUÉ` (aucune nouvelle position) **ou** `TAILLE_RÉDUITE`
  - Sinon → `TRADE_OK`
- Objectif : éviter les mèches violentes et imprévisibles.
- Fréquence : chargement quotidien du calendrier.

### Couche 4 — Technique (déclencheur)
- **Stratégie** : V3 Trend Rider — EMA 50/200 + MACD + ADX, plus zones **supply/demand** et structure (swing highs/lows, cassures de structure / BOS).
- **Règle** : le signal ne se déclenche que :
  1. dans le **sens autorisé** par la couche 1,
  2. si la couche 2 n'est pas `SATURÉ` dans ce sens,
  3. si la couche 3 dit `TRADE_OK` (ou taille réduite).
- C'est **seulement ici** qu'un ordre est proposé.

---

## 3. Gestion du risque & espérance

Le cœur du système. Le robot ne vise pas un taux de réussite élevé, mais une **espérance positive** :

```
Espérance = (taux_réussite × gain_moyen) − (taux_échec × perte_moyenne)
```

- Viser un **ratio gain/perte élevé** (ex. risquer 1 pour viser 2 à 3).
- Avec un R:R de 1:3, un taux de réussite de **40 %** suffit à être largement gagnant.
- **Loguer l'espérance en continu** : tant qu'elle est positive, le système est sain. Si elle passe négative → alerte, ne pas ajouter de couche "au feeling", revoir les règles.
- Risque par trade : fixe et petit (ex. 1 % du capital), stop-loss **toujours** défini avant l'entrée.

---

## 4. Garde-fous (non négociables)

- **Humain dans la boucle** : le robot **propose**, il n'exécute pas seul. C'est un copilote, pas un pilote.
- **Aucune donnée publique n'est prédictive.** Les couches servent à *éliminer les mauvais trades*, pas à deviner l'avenir.
- La jauge "résumé des indicateurs" (TradingView) = couche technique déjà couverte par la couche 4 → **ne pas** la traiter comme un signal indépendant.
- Ne jamais entrer juste parce qu'un indicateur dit "Achat fort" : en tendance forte c'est souvent le sommet.

---

## 5. Architecture technique suggérée

Découpage en modules Python indépendants (chacun testable seul) :

```
gold_bot/
├── data/
│   ├── macro.py         # récupère DFII10 (FRED) + DXY  -> couche 1
│   ├── cot.py           # télécharge COT CFTC, calcule le z-score 3 ans -> couche 2
│   └── calendar.py      # charge le calendrier éco       -> couche 3
├── strategy/
│   ├── indicators.py    # EMA / MACD / ADX (calcul déterministe)
│   ├── structure.py     # swing highs/lows, supply/demand, BOS
│   └── trend_rider.py   # V3 Trend Rider -> couche 4
├── engine/
│   ├── funnel.py        # applique les 4 couches dans l'ordre
│   └── risk.py          # sizing, stop, log de l'espérance
└── main.py              # orchestration + sortie (proposition de trade)
```

### Flux de décision (logique)

```
1. biais      = macro.get_bias()              # LONG_ONLY / SHORT_ONLY / NEUTRE
2. si biais == NEUTRE            -> STOP (rien à faire)
3. positionnement = cot.get_state()           # OK / SATURÉ_LONG / SATURÉ_SHORT
4. si positionnement sature le sens du biais -> STOP
5. calendrier = calendar.check()              # TRADE_OK / BLOQUÉ / TAILLE_RÉDUITE
6. si calendrier == BLOQUÉ       -> STOP
7. signal     = trend_rider.check(biais)      # entrée technique dans le bon sens
8. si signal  -> risk.size(signal, calendrier) -> PROPOSER LE TRADE (validation humaine)
```

---

## 6. Sources de données (rappel)

| Donnée | Où | Coût | Fréquence |
|--------|-----|------|-----------|
| Taux réels (`DFII10`) | FRED | Gratuit | Quotidien |
| DXY | FRED / broker | Gratuit | Quotidien |
| COT (Disaggregated, Managed Money) | cftc.gov (téléchargeable) | Gratuit | Hebdo (vendredi) |
| Calendrier éco | ForexFactory / Investing.com | Gratuit | Quotidien |
| Prix OHLC gold | Capital.com API / broker | Selon broker | Selon TF |

---

## 7. Ordre de développement conseillé

1. **Couche 4 seule** (tu l'as déjà en grande partie) → backtest de référence.
2. Ajouter **Couche 3** (calendrier) → mesurer l'effet sur l'espérance.
3. Ajouter **Couche 1** (biais macro) → mesurer.
4. Ajouter **Couche 2** (COT) → mesurer.
5. Comparer l'espérance à chaque étape : **chaque couche doit améliorer (ou au moins ne pas dégrader)** l'espérance. Si une couche n'apporte rien, elle dégage.
