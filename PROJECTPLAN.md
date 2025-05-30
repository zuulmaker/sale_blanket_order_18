# Odoo 18.0 Migration Projekt: sale_blanket_order

## Projekt-Übersicht

**Ziel**: Migration des OCA sale_blanket_order Moduls von Version 17.0 zu 18.0  
**Prinzipien**: Fehlertolerant, Idempotent, Robuste Implementierung  
**Projektstart**: 30.05.2025  

## Projekt-Struktur

```
sale_blanket_order_18/
├── __init__.py                           ⚠️ KERN-DATEI
├── __manifest__.py                       ⚠️ KERN-DATEI
├── README.rst                           📝 DOKUMENTATION
├── models/
│   ├── __init__.py                      ⚠️ KERN-DATEI
│   ├── sale_blanket_orders.py            ⚠️ KERN-DATEI
│   ├── sale_blanket_order_line.py       ⚠️ KERN-DATEI
│   └── sale_order.py                    ⚠️ KERN-DATEI
├── wizards/
│   ├── __init__.py                      🔧 FUNKTIONAL
│   └── sale_blanket_order_wizard.py     🔧 FUNKTIONAL
├── views/
│   ├── sale_blanket_order_views.xml     🎨 UI-DATEI
│   ├── sale_order_views.xml             🎨 UI-DATEI
│   └── wizard_views.xml                 🎨 UI-DATEI
├── security/
│   └── ir.model.access.csv              🔒 SICHERHEIT
├── data/
│   ├── sequence_data.xml                📊 DATEN
│   └── mail_template_data.xml           📊 DATEN
├── migrations/
│   └── 18.0.1.0.0/
│       ├── pre-migration.py             🔄 MIGRATION
│       └── post-migration.py            🔄 MIGRATION
├── tests/
│   ├── __init__.py                      🧪 TESTS
│   ├── test_sale_blanket_order.py       🧪 TESTS
│   └── test_migration.py                🧪 TESTS
└── static/
    └── description/
        ├── icon.png                     🖼️ ASSETS
        └── index.html                   🖼️ ASSETS
```

## Migration Roadmap

### Phase 1: Kern-Migration (PRIORITÄT 1) ⚠️

| Status | Datei | Beschreibung | Anwendungsbeispiel |
|--------|-------|--------------|-------------------|
| ⭕ | `__manifest__.py` | Version von 17.0.1.0.0 → 18.0.1.0.0 | Verhindert Versionskonflikte |
| ⭕ | `__init__.py` | Migration Hooks hinzufügen | Idempotente Initialisierung |
| ⭕ | `models/__init__.py` | Model-Imports aktualisieren | Fehlertolerant laden |
| ⭕ | `models/sale_blanket_orders.py` | Hauptmodell robuster machen | Exception Handling für Compute-Methoden |

**Warum zuerst**: Diese Dateien sind für die Grundfunktionalität zwingend erforderlich.

### Phase 2: Modell-Verbesserungen (PRIORITÄT 2) ⚠️

| Status | Datei | Beschreibung | Anwendungsbeispiel |
|--------|-------|--------------|-------------------|
| ⭕ | `models/sale_blanket_order_line.py` | Line-Model erweitern | Robuste Mengen-Berechnung |
| ⭕ | `models/sale_order.py` | Sale Order Integration | Fehlertolerant bei Blanket Order Zuordnung |

### Phase 3: Funktionale Erweiterungen (PRIORITÄT 3) 🔧

| Status | Datei | Beschreibung | Anwendungsbeispiel |
|--------|-------|--------------|-------------------|
| ⭕ | `wizards/__init__.py` | Wizard-Initialisierung | - |
| ⭕ | `wizards/sale_blanket_order_wizard.py` | SO-Erstellung Wizard | Idempotente Bestellerstellung |

### Phase 4: Benutzeroberfläche (PRIORITÄT 4) 🎨

| Status | Datei | Beschreibung | Anwendungsbeispiel |
|--------|-------|--------------|-------------------|
| ⭕ | `views/sale_blanket_order_views.xml` | Hauptformular | Robuste XML-Views mit Fallbacks |
| ⭕ | `views/sale_order_views.xml` | SO-Erweiterungen | Fehlertolerant bei fehlendem Blanket Order |
| ⭕ | `views/wizard_views.xml` | Wizard-Interface | Benutzerfreundliche Wizard-Dialoge |

### Phase 5: Sicherheit & Daten (PRIORITÄT 5) 📊

| Status | Datei | Beschreibung | Anwendungsbeispiel |
|--------|-------|--------------|-------------------|
| ⭕ | `security/ir.model.access.csv` | Zugriffsrechte | Sichere Berechtigungen für alle Benutzergruppen |
| ⭕ | `data/sequence_data.xml` | Nummernkreise | Eindeutige Blanket Order Nummern |
| ⭕ | `data/mail_template_data.xml` | E-Mail Vorlagen | Automatische Benachrichtigungen |

### Phase 6: Migration & Wartung (PRIORITÄT 6) 🔄

| Status | Datei | Beschreibung | Anwendungsbeispiel |
|--------|-------|--------------|-------------------|
| ⭕ | `migrations/18.0.1.0.0/pre-migration.py` | Vor-Migration | Datenbank-Backup, Integritätsprüfung |
| ⭕ | `migrations/18.0.1.0.0/post-migration.py` | Nach-Migration | Datenbereinigung, Feld-Migration |

### Phase 7: Testing & Dokumentation (PRIORITÄT 7) 🧪

| Status | Datei | Beschreibung | Anwendungsbeispiel |
|--------|-------|--------------|-------------------|
| ⭕ | `tests/__init__.py` | Test-Setup | - |
| ⭕ | `tests/test_sale_blanket_order.py` | Funktions-Tests | Automatisierte Tests für alle Features |
| ⭕ | `tests/test_migration.py` | Migrations-Tests | Idempotenz-Tests |
| ⭕ | `README.rst` | Dokumentation | Installations- und Nutzungsanleitung |

## Arbeitsweise

### 1. Reihenfolge einhalten
- **Immer** mit Phase 1 beginnen (Kern-Migration)
- **Niemals** Phasen überspringen
- **Jede Datei** einzeln als Artefakt erstellen

### 2. Fehlertolerant entwickeln
```python
# ✅ RICHTIG: Immer try-catch verwenden
try:
    result = self.compute_something()
    return result or default_value
except Exception as e:
    _logger.warning(f"Fehler bei compute_something: {e}")
    return default_value

# ❌ FALSCH: Keine Fehlerbehandlung
result = self.compute_something()
return result
```

### 3. Idempotent programmieren
```python
# ✅ RICHTIG: Prüfung vor Änderung
if not self.exists():
    return False
    
if self.state != 'draft':
    _logger.info("Bereits bestätigt - keine Aktion nötig")
    return True

# ❌ FALSCH: Blindes Ausführen
self.write({'state': 'confirmed'})
```

## Artefakt-Erstellung Workflow

### Schritt 1: Datei auswählen
1. Nächste Datei aus aktueller Phase wählen
2. Status auf "🔄 IN ARBEIT" setzen

### Schritt 2: Artefakt erstellen
1. **Titel-Format**: `[PHASE-NR] Dateiname - Beschreibung`
2. **Beispiel**: `[Phase 1] __manifest__.py - Kern-Migration auf 18.0`

### Schritt 3: Code implementieren
- **Immer** deutsche Kommentare
- **Immer** Exception Handling
- **Immer** Logging verwenden

### Schritt 4: Validierung
1. Code auf Fehlertolleranz prüfen
2. Idempotenz sicherstellen
3. Status auf "✅ ERLEDIGT" setzen

## Migration Commands

### Vor Migration (Sicherheit)
```bash
# Backup erstellen
pg_dump your_database > backup_17_$(date +%Y%m%d).sql

# Module deaktivieren
odoo -d your_database -u sale_blanket_order --stop-after-init
```

### Migration durchführen
```bash
# Module installieren
odoo -d your_database -i sale_blanket_order --stop-after-init

# Module upgraden (idempotent)
odoo -d your_database -u sale_blanket_order --stop-after-init
```

### Nach Migration (Validierung)
```bash
# Tests ausführen
odoo -d your_database --test-enable --stop-after-init

# Logs prüfen
tail -f /var/log/odoo/odoo.log | grep -i blanket
```

## Qualitätskontrolle

### Checkliste pro Datei ✅

- [ ] Deutsche Kommentare vorhanden
- [ ] Exception Handling implementiert
- [ ] Logging konfiguriert
- [ ] Idempotenz gewährleistet
- [ ] Fehlertolleranz getestet
- [ ] Rückwärtskompatibilität geprüft

### Checkliste Gesamt-Migration ✅

- [ ] Alle 7 Phasen abgeschlossen
- [ ] Migration mindestens 2x getestet
- [ ] Rollback-Plan erstellt
- [ ] Dokumentation aktualisiert
- [ ] Performance validiert
- [ ] Security Review durchgeführt

## Nächste Schritte

1. **JETZT**: Phase 1 starten mit `__manifest__.py`
2. **Dann**: Systematisch durch alle Phasen arbeiten
3. **Schließlich**: Comprehensive Testing

---

**Projekt-Status**: 🚀 BEREIT ZUM START  
**Nächste Aktion**: Erstelle Artefakt für `__manifest__.py`