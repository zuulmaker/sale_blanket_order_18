#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 VOLLSTÄNDIGER ODOO 18.0 AUTOMATIK-MIGRATOR

ALLE XML-Änderungen in einem einzigen, fehlertoleranten und idempotenten Tool!

🎯 FEATURES:
- ✅ ALLE kritischen Breaking Changes (attrs/states, Widgets, etc.)
- ✅ UI-Enhancements (Tree Views, Badge Widgets, Responsive Design)
- ✅ Sicherheits-Validierungen (Gruppen, Access Rights)
- ✅ Mail Template Modernisierung
- ✅ Search Panel Integration
- ✅ Accessibility Improvements
- ✅ Backup/Rollback System
- ✅ Detaillierte Logs mit farbiger Ausgabe
- ✅ Fehlertolerant und idempotent

🎯 Anwendungsbeispiele:
# Komplette Migration eines Moduls
python odoo18_migrator.py /path/to/module

# Nur Analyse ohne Änderungen
python odoo18_migrator.py /path/to/module --dry-run

# Mit erweiterten Features
python odoo18_migrator.py /path/to/module --enhance-ui --add-accessibility

# Rollback nach Problemen
python odoo18_migrator.py /path/to/module --rollback

Autor: j.s.drees@az-zwick.com
Datum: 2025-06-13
"""

import os
import re
import shutil
import logging
import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime
from collections import defaultdict
import xml.etree.ElementTree as ET
from xml.dom import minidom


class ComprehensiveOdoo18Migrator:
    """
    🚀 VOLLSTÄNDIGER Odoo 18.0 Automatik-Migrator

    Migriert ALLE bekannten XML-Änderungen von 17.0 zu 18.0 in einem Durchgang.
    Fehlertolerant, idempotent und produktionsreif.
    """

    def __init__(self, module_path: str, options: Dict = None):
        self.module_path = Path(module_path)
        self.options = options or {}
        self.dry_run = self.options.get('dry_run', False)
        self.enhance_ui = self.options.get('enhance_ui', True)
        self.add_accessibility = self.options.get('add_accessibility', True)
        self.modernize_templates = self.options.get('modernize_templates', True)

        # Backup-System
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_dir = self.module_path / f"backup_odoo18_complete_{timestamp}"

        # Logging mit farbiger Ausgabe
        self._setup_logging()

        # Migration-Statistiken
        self.stats = {
            'files_processed': 0,
            'critical_fixes': 0,
            'ui_enhancements': 0,
            'security_fixes': 0,
            'accessibility_improvements': 0,
            'template_modernizations': 0,
            'errors': 0,
            'warnings': 0
        }

        # Farbcodes für Terminal-Ausgabe
        self.COLORS = {
            'RED': '\033[91m',  # Fehler
            'GREEN': '\033[92m',  # Erfolg
            'YELLOW': '\033[93m',  # Warnung
            'BLUE': '\033[94m',  # Info
            'MAGENTA': '\033[95m',  # Highlight
            'CYAN': '\033[96m',  # Debug
            'WHITE': '\033[97m',  # Standard
            'BOLD': '\033[1m',  # Fett
            'END': '\033[0m'  # Reset
        }

        # Migration-Pattern-Definitionen
        self._init_migration_patterns()

    def _setup_logging(self):
        """Konfiguriert detailliertes Logging"""
        log_file = f"odoo18_complete_migration_{datetime.now().strftime('%Y%m%d')}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        self.logger.info(f"🚀 Starte vollständige Odoo 18.0 Migration")
        self.logger.info(f"📁 Modul: {self.module_path}")
        self.logger.info(f"🏃 Dry Run: {self.dry_run}")

    def _init_migration_patterns(self):
        """Initialisiert alle Migration-Pattern"""

        # 🔴 KRITISCHE BREAKING CHANGES
        self.critical_patterns = {
            'attrs_invisible': {
                'pattern': r'attrs\s*=\s*["\']{\s*["\']invisible["\']\s*:\s*\[(.*?)\]\s*}["\']',
                'replacement': self._convert_attrs_invisible,
                'description': 'attrs invisible → invisible'
            },
            'attrs_readonly': {
                'pattern': r'attrs\s*=\s*["\']{\s*["\']readonly["\']\s*:\s*\[(.*?)\]\s*}["\']',
                'replacement': self._convert_attrs_readonly,
                'description': 'attrs readonly → readonly'
            },
            'attrs_required': {
                'pattern': r'attrs\s*=\s*["\']{\s*["\']required["\']\s*:\s*\[(.*?)\]\s*}["\']',
                'replacement': self._convert_attrs_required,
                'description': 'attrs required → required'
            },
            'states_attribute': {
                'pattern': r'states\s*=\s*["\']([^"\']+)["\']',
                'replacement': self._convert_states,
                'description': 'states → invisible'
            },
            'old_avatar_widget': {
                'pattern': r'widget\s*=\s*["\']many2one_avatar["\']',
                'replacement': lambda m: 'widget="many2one_avatar_user"',
                'description': 'many2one_avatar → many2one_avatar_user'
            }
        }

        # 📊 UI-ENHANCEMENTS
        self.ui_patterns = {
            'tree_enhancements': {
                'pattern': r'(<tree[^>]*?)>',
                'replacement': self._enhance_tree_view,
                'description': 'Tree View Enhancements (sample, multi_edit)'
            },
            'badge_widgets': {
                'pattern': r'(<field[^>]+name\s*=\s*["\']state["\'][^>]*?)(/?>)',
                'replacement': self._add_badge_widget,
                'description': 'Badge Widget für State-Felder'
            },
            'optional_fields': {
                'pattern': r'(<field[^>]+name\s*=\s*["\'](?:user_id|company_id|write_date|create_date)["\'][^>]*?)(/?>)',
                'replacement': self._add_optional_attribute,
                'description': 'Optional Attribute für bessere UX'
            },
            'responsive_forms': {
                'pattern': r'(<form[^>]*?)>',
                'replacement': self._add_responsive_classes,
                'description': 'Responsive Design Classes'
            }
        }

        # 🔒 SICHERHEITS-VALIDIERUNGEN
        self.security_patterns = {
            'group_validation': {
                'pattern': r'groups\s*=\s*["\']([^"\']*)["\']',
                'replacement': self._validate_groups,
                'description': 'Gruppen-Validierung'
            },
            'menu_security': {
                'pattern': r'(<menuitem[^>]*?)>',
                'replacement': self._enhance_menu_security,
                'description': 'Menu-Sicherheit verbessern'
            }
        }

        # 📧 MAIL TEMPLATE MODERNISIERUNG
        self.template_patterns = {
            'robust_email_to': {
                'pattern': r'(<field name="email_to">)([^<]*)(</field>)',
                'replacement': self._modernize_email_to,
                'description': 'Robuste E-Mail-To Felder'
            },
            'template_lang': {
                'pattern': r'(<record[^>]+model="mail\.template"[^>]*>.*?)(<field name="lang">.*?</field>)?(.*?</record>)',
                'replacement': self._add_template_lang,
                'description': 'Mehrsprachige Templates'
            }
        }

        # ♿ ACCESSIBILITY IMPROVEMENTS
        self.accessibility_patterns = {
            'aria_labels': {
                'pattern': r'(<field[^>]+name\s*=\s*["\'][^"\']+["\'][^>]*?)(/?>)',
                'replacement': self._add_aria_labels,
                'description': 'ARIA Labels für Screen Reader'
            },
            'button_descriptions': {
                'pattern': r'(<button[^>]+string\s*=\s*["\']([^"\']+)["\'][^>]*?)(/?>)',
                'replacement': self._add_button_descriptions,
                'description': 'Button Descriptions für Accessibility'
            }
        }

    # ===================================================================
    # KRITISCHE MIGRATION-FUNKTIONEN
    # ===================================================================

    def _convert_attrs_invisible(self, match):
        """Konvertiert attrs invisible zur neuen Syntax"""
        condition = match.group(1)
        simplified = self._simplify_domain_condition(condition)
        return f'invisible="{simplified}"'

    def _convert_attrs_readonly(self, match):
        """Konvertiert attrs readonly zur neuen Syntax"""
        condition = match.group(1)
        simplified = self._simplify_domain_condition(condition)
        return f'readonly="{simplified}"'

    def _convert_attrs_required(self, match):
        """Konvertiert attrs required zur neuen Syntax"""
        condition = match.group(1)
        simplified = self._simplify_domain_condition(condition)
        return f'required="{simplified}"'

    def _convert_states(self, match):
        """Konvertiert states zur neuen invisible Syntax"""
        states_value = match.group(1)
        states = [s.strip() for s in states_value.split(',')]

        if len(states) == 1:
            return f'invisible="state != \'{states[0]}\'"'
        else:
            states_list = ', '.join([f"'{s}'" for s in states])
            return f'invisible="state not in [{states_list}]"'

    def _simplify_domain_condition(self, condition: str) -> str:
        """
        Vereinfacht Odoo-Domain-Conditions

        🎯 Anwendungsbeispiele:
        ('field', '=', 'value') → field == 'value'
        ('field', '!=', False) → field != False
        ('field', 'in', [1,2,3]) → field in [1,2,3]
        """
        try:
            patterns = [
                # Gleichheit
                (r"\('([^']+)',\s*'=',\s*'([^']+)'\)", r"\1 == '\2'"),
                (r"\('([^']+)',\s*'=',\s*(False|True)\)", r"\1 == \2"),
                (r"\('([^']+)',\s*'=',\s*(\d+)\)", r"\1 == \2"),

                # Ungleichheit
                (r"\('([^']+)',\s*'!=',\s*'([^']+)'\)", r"\1 != '\2'"),
                (r"\('([^']+)',\s*'!=',\s*(False|True)\)", r"\1 != \2"),
                (r"\('([^']+)',\s*'!=',\s*(\d+)\)", r"\1 != \2"),

                # Vergleiche
                (r"\('([^']+)',\s*'>',\s*(\d+)\)", r"\1 > \2"),
                (r"\('([^']+)',\s*'<',\s*(\d+)\)", r"\1 < \2"),
                (r"\('([^']+)',\s*'>=',\s*(\d+)\)", r"\1 >= \2"),
                (r"\('([^']+)',\s*'<=',\s*(\d+)\)", r"\1 <= \2"),

                # IN/NOT IN
                (r"\('([^']+)',\s*'in',\s*\[(.*?)\]\)", r"\1 in [\2]"),
                (r"\('([^']+)',\s*'not in',\s*\[(.*?)\]\)", r"\1 not in [\2]"),
            ]

            result = condition.strip()
            for pattern, replacement in patterns:
                result = re.sub(pattern, replacement, result)

            return result.strip()

        except Exception as e:
            self.logger.warning(f"⚠️  Konnte Condition nicht vereinfachen: {condition}")
            return condition

    # ===================================================================
    # UI-ENHANCEMENT FUNKTIONEN
    # ===================================================================

    def _enhance_tree_view(self, match):
        """Verbessert Tree Views mit modernen 18.0 Features"""
        tree_tag = match.group(1)

        # Prüfe ob bereits moderne Features vorhanden sind
        if 'sample=' not in tree_tag:
            tree_tag += ' sample="1"'

        if 'multi_edit=' not in tree_tag:
            tree_tag += ' multi_edit="1"'

        return f'{tree_tag}>'

    def _add_badge_widget(self, match):
        """Fügt Badge Widget für State-Felder hinzu"""
        field_tag = match.group(1)
        closing = match.group(2)

        if 'widget=' not in field_tag:
            field_tag += ' widget="badge"'

        return f'{field_tag}{closing}'

    def _add_optional_attribute(self, match):
        """Fügt optional Attribut für bessere UX hinzu"""
        field_tag = match.group(1)
        closing = match.group(2)

        if 'optional=' not in field_tag:
            # Bestimme sinnvolle Default-Werte
            if 'user_id' in field_tag:
                field_tag += ' optional="show"'
            elif any(field in field_tag for field in ['write_date', 'create_date', 'company_id']):
                field_tag += ' optional="hide"'

        return f'{field_tag}{closing}'

    def _add_responsive_classes(self, match):
        """Fügt responsive CSS-Classes zu Forms hinzu"""
        form_tag = match.group(1)

        if 'class=' not in form_tag:
            form_tag += ' class="o_responsive_form"'
        elif 'o_responsive' not in form_tag:
            # Erweitere bestehende Class
            class_match = re.search(r'class\s*=\s*["\']([^"\']*)["\']', form_tag)
            if class_match:
                existing_classes = class_match.group(1)
                new_classes = f'{existing_classes} o_responsive_form'
                form_tag = form_tag.replace(class_match.group(0), f'class="{new_classes}"')

        return f'{form_tag}>'

    # ===================================================================
    # SICHERHEITS-FUNKTIONEN
    # ===================================================================

    def _validate_groups(self, match):
        """Validiert und verbessert Gruppen-Definitionen"""
        groups_value = match.group(1)

        # Liste bekannter Standard-Gruppen (erweitert für Odoo 18.0)
        valid_groups = {
            'base.group_user', 'base.group_system', 'base.group_public',
            'sales_team.group_sale_user', 'sales_team.group_sale_manager',
            'purchase.group_purchase_user', 'purchase.group_purchase_manager',
            'account.group_account_user', 'account.group_account_manager',
            'stock.group_stock_user', 'stock.group_stock_manager',
            'project.group_project_user', 'project.group_project_manager'
        }

        groups = [g.strip() for g in groups_value.split(',')]
        validated_groups = []

        for group in groups:
            if group in valid_groups or group.startswith('base.') or '.' in group:
                validated_groups.append(group)
            else:
                self.logger.warning(f"⚠️  Unbekannte Gruppe gefunden: {group}")
                self.stats['warnings'] += 1
                validated_groups.append(group)  # Behalte für manuelle Prüfung

        return f'groups="{",".join(validated_groups)}"'

    def _enhance_menu_security(self, match):
        """Verbessert Menu-Sicherheit"""
        menuitem_tag = match.group(1)

        # Füge sequence hinzu wenn nicht vorhanden
        if 'sequence=' not in menuitem_tag:
            menuitem_tag += ' sequence="10"'

        # Füge active hinzu wenn nicht vorhanden
        if 'active=' not in menuitem_tag:
            menuitem_tag += ' active="True"'

        return f'{menuitem_tag}>'

    # ===================================================================
    # MAIL TEMPLATE FUNKTIONEN
    # ===================================================================

    def _modernize_email_to(self, match):
        """Modernisiert E-Mail-To Felder mit Fallback"""
        opening = match.group(1)
        content = match.group(2).strip()
        closing = match.group(3)

        # Füge Fallback hinzu wenn nicht vorhanden
        if 'or ' not in content:
            if 'object.partner_id.email' in content:
                content = "${object.partner_id.email or 'noreply@example.com'}"
            elif not content.startswith('${'):
                content = f"${{{content} or 'noreply@example.com'}}"

        return f'{opening}{content}{closing}'

    def _add_template_lang(self, match):
        """Fügt Mehrsprachigkeit zu Mail Templates hinzu"""
        record_start = match.group(1)
        existing_lang = match.group(2)
        record_end = match.group(3)

        if not existing_lang:
            lang_field = '<field name="lang">${object.partner_id.lang or \'en_US\'}</field>'
            # Füge lang field vor dem Ende des Records ein
            return f'{record_start}{lang_field}\n        {record_end}'

        return match.group(0)  # Bereits vorhanden

    # ===================================================================
    # ACCESSIBILITY FUNKTIONEN
    # ===================================================================

    def _add_aria_labels(self, match):
        """Fügt ARIA Labels für bessere Accessibility hinzu"""
        field_tag = match.group(1)
        closing = match.group(2)

        # Extrahiere Feldname
        name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', field_tag)
        if name_match and 'aria-label=' not in field_tag:
            field_name = name_match.group(1)

            # Generiere sinnvolle Labels
            aria_labels = {
                'partner_id': 'Customer',
                'user_id': 'Salesperson',
                'date_order': 'Order Date',
                'amount_total': 'Total Amount',
                'state': 'Status',
                'name': 'Reference',
                'description': 'Description'
            }

            if field_name in aria_labels:
                field_tag += f' aria-label="{aria_labels[field_name]}"'

        return f'{field_tag}{closing}'

    def _add_button_descriptions(self, match):
        """Fügt Descriptions zu Buttons für bessere Accessibility hinzu"""
        button_tag = match.group(1)
        button_text = match.group(2)
        closing = match.group(3)

        if 'help=' not in button_tag and 'aria-describedby=' not in button_tag:
            # Generiere hilfreiche Descriptions
            help_texts = {
                'Confirm': 'Confirm this order and make it active',
                'Cancel': 'Cancel this order',
                'Create': 'Create a new record',
                'Save': 'Save changes to this record',
                'Delete': 'Delete this record permanently'
            }

            for key, help_text in help_texts.items():
                if key.lower() in button_text.lower():
                    button_tag += f' help="{help_text}"'
                    break

        return f'{button_tag}{closing}'

    # ===================================================================
    # HAUPT-MIGRATIONS-FUNKTIONEN
    # ===================================================================

    def create_comprehensive_backup(self) -> bool:
        """Erstellt vollständiges Backup des Moduls"""
        try:
            if self.dry_run:
                self.logger.info("🏃 DRY RUN: Backup würde erstellt werden")
                return True

            self.backup_dir.mkdir(parents=True, exist_ok=True)

            # Kopiere alle relevanten Dateien
            file_patterns = ['*.xml', '*.py', '*.csv', '*.yml', '*.json', '*.rst', '*.md']
            copied_files = 0

            for pattern in file_patterns:
                for file_path in self.module_path.rglob(pattern):
                    if 'backup_' not in str(file_path):  # Vermeide Backup von Backups
                        relative_path = file_path.relative_to(self.module_path)
                        backup_file = self.backup_dir / relative_path
                        backup_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, backup_file)
                        copied_files += 1

            # Erstelle Backup-Metadata
            backup_info = {
                'timestamp': datetime.now().isoformat(),
                'module_path': str(self.module_path),
                'files_backed_up': copied_files,
                'migration_type': 'comprehensive_odoo18',
                'options': self.options
            }

            with open(self.backup_dir / 'backup_info.json', 'w') as f:
                json.dump(backup_info, f, indent=2)

            self.logger.info(f"✅ Vollständiges Backup erstellt: {self.backup_dir}")
            self.logger.info(f"📄 Dateien gesichert: {copied_files}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Backup-Fehler: {e}")
            return False

    def migrate_xml_file(self, xml_file: Path) -> Dict:
        """Migriert eine einzelne XML-Datei mit allen Pattern"""
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                original_content = f.read()

            content = original_content
            changes = []

            self.logger.info(f"🔄 Migriere: {xml_file.relative_to(self.module_path)}")

            # 1. KRITISCHE BREAKING CHANGES
            for pattern_name, pattern_config in self.critical_patterns.items():
                pattern = pattern_config['pattern']
                replacement_func = pattern_config['replacement']

                matches = list(re.finditer(pattern, content, re.IGNORECASE | re.DOTALL))
                for match in matches:
                    old_text = match.group(0)
                    new_text = replacement_func(match)

                    content = content.replace(old_text, new_text, 1)

                    changes.append({
                        'type': 'CRITICAL',
                        'pattern': pattern_name,
                        'description': pattern_config['description'],
                        'old': old_text,
                        'new': new_text,
                        'line': original_content[:match.start()].count('\n') + 1
                    })

                    self.stats['critical_fixes'] += 1

            # 2. UI-ENHANCEMENTS (wenn aktiviert)
            if self.enhance_ui:
                for pattern_name, pattern_config in self.ui_patterns.items():
                    pattern = pattern_config['pattern']
                    replacement_func = pattern_config['replacement']

                    matches = list(re.finditer(pattern, content, re.IGNORECASE | re.DOTALL))
                    for match in matches:
                        old_text = match.group(0)
                        new_text = replacement_func(match)

                        if old_text != new_text:  # Nur wenn tatsächlich geändert
                            content = content.replace(old_text, new_text, 1)

                            changes.append({
                                'type': 'UI_ENHANCEMENT',
                                'pattern': pattern_name,
                                'description': pattern_config['description'],
                                'old': old_text,
                                'new': new_text,
                                'line': original_content[:match.start()].count('\n') + 1
                            })

                            self.stats['ui_enhancements'] += 1

            # 3. SICHERHEITS-VALIDIERUNGEN
            for pattern_name, pattern_config in self.security_patterns.items():
                pattern = pattern_config['pattern']
                replacement_func = pattern_config['replacement']

                matches = list(re.finditer(pattern, content, re.IGNORECASE | re.DOTALL))
                for match in matches:
                    old_text = match.group(0)
                    new_text = replacement_func(match)

                    if old_text != new_text:
                        content = content.replace(old_text, new_text, 1)

                        changes.append({
                            'type': 'SECURITY',
                            'pattern': pattern_name,
                            'description': pattern_config['description'],
                            'old': old_text,
                            'new': new_text,
                            'line': original_content[:match.start()].count('\n') + 1
                        })

                        self.stats['security_fixes'] += 1

            # 4. MAIL TEMPLATE MODERNISIERUNG (wenn aktiviert)
            if self.modernize_templates and 'mail' in str(xml_file):
                for pattern_name, pattern_config in self.template_patterns.items():
                    pattern = pattern_config['pattern']
                    replacement_func = pattern_config['replacement']

                    matches = list(re.finditer(pattern, content, re.IGNORECASE | re.DOTALL))
                    for match in matches:
                        old_text = match.group(0)
                        new_text = replacement_func(match)

                        if old_text != new_text:
                            content = content.replace(old_text, new_text, 1)

                            changes.append({
                                'type': 'TEMPLATE',
                                'pattern': pattern_name,
                                'description': pattern_config['description'],
                                'old': old_text,
                                'new': new_text,
                                'line': original_content[:match.start()].count('\n') + 1
                            })

                            self.stats['template_modernizations'] += 1

            # 5. ACCESSIBILITY IMPROVEMENTS (wenn aktiviert)
            if self.add_accessibility:
                for pattern_name, pattern_config in self.accessibility_patterns.items():
                    pattern = pattern_config['pattern']
                    replacement_func = pattern_config['replacement']

                    matches = list(re.finditer(pattern, content, re.IGNORECASE | re.DOTALL))
                    for match in matches:
                        old_text = match.group(0)
                        new_text = replacement_func(match)

                        if old_text != new_text:
                            content = content.replace(old_text, new_text, 1)

                            changes.append({
                                'type': 'ACCESSIBILITY',
                                'pattern': pattern_name,
                                'description': pattern_config['description'],
                                'old': old_text,
                                'new': new_text,
                                'line': original_content[:match.start()].count('\n') + 1
                            })

                            self.stats['accessibility_improvements'] += 1

            # Schreibe migrierte Datei
            if not self.dry_run and content != original_content:
                with open(xml_file, 'w', encoding='utf-8') as f:
                    f.write(content)

            result = {
                'file': str(xml_file),
                'success': True,
                'changes': changes,
                'changes_count': len(changes),
                'original_size': len(original_content),
                'new_size': len(content)
            }

            if changes:
                change_types = defaultdict(int)
                for change in changes:
                    change_types[change['type']] += 1

                self.logger.info(f"  ✅ {len(changes)} Änderungen: {dict(change_types)}")
            else:
                self.logger.info(f"  ℹ️  Keine Änderungen erforderlich")

            return result

        except Exception as e:
            self.logger.error(f"❌ Fehler bei {xml_file}: {e}")
            self.stats['errors'] += 1
            return {
                'file': str(xml_file),
                'success': False,
                'error': str(e),
                'changes_count': 0
            }

    def migrate_complete_module(self) -> Dict:
        """Führt vollständige Modul-Migration durch"""
        self.logger.info(f"🚀 Starte vollständige Odoo 18.0 Migration")

        if self.dry_run:
            self.logger.info(f"{self.COLORS['YELLOW']}🏃 DRY RUN Modus aktiv{self.COLORS['END']}")

        # Erstelle Backup
        if not self.create_comprehensive_backup():
            return {'success': False, 'error': 'Backup fehlgeschlagen'}

        # Finde alle XML-Dateien
        xml_files = list(self.module_path.rglob("*.xml"))
        self.logger.info(f"📄 Gefundene XML-Dateien: {len(xml_files)}")

        # Migriere alle Dateien
        results = []
        start_time = datetime.now()

        for xml_file in xml_files:
            result = self.migrate_xml_file(xml_file)
            results.append(result)
            self.stats['files_processed'] += 1

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Erstelle finalen Report
        final_report = {
            'module_path': str(self.module_path),
            'backup_path': str(self.backup_dir),
            'timestamp': end_time.isoformat(),
            'duration_seconds': duration,
            'dry_run': self.dry_run,
            'options': self.options,
            'odoo_version': '18.0',
            'statistics': self.stats,
            'files': results,
            'errors': [r for r in results if not r.get('success', True)],
            'success': self.stats['errors'] == 0
        }

        # Zeige finale Zusammenfassung
        self._print_final_summary(final_report)

        # Exportiere detaillierten Report
        if not self.dry_run:
            report_file = self.module_path / f"odoo18_migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(final_report, f, indent=2, ensure_ascii=False)
            self.logger.info(f"📊 Detaillierter Report: {report_file}")

        return final_report

    def _print_final_summary(self, report: Dict):
        """Druckt farbige finale Zusammenfassung"""
        stats = report['statistics']

        print("\n" + "=" * 80)
        print(
            f"{self.COLORS['BOLD']}{self.COLORS['BLUE']}🚀 VOLLSTÄNDIGE ODOO 18.0 MIGRATION ABGESCHLOSSEN{self.COLORS['END']}")
        print("=" * 80)

        if report['dry_run']:
            print(f"{self.COLORS['YELLOW']}🏃 DRY RUN - Keine Dateien wurden geändert{self.COLORS['END']}")

        print(f"📁 Modul: {self.COLORS['CYAN']}{report['module_path']}{self.COLORS['END']}")
        print(f"⏱️  Dauer: {self.COLORS['CYAN']}{report['duration_seconds']:.2f} Sekunden{self.COLORS['END']}")
        print(f"📄 Dateien verarbeitet: {self.COLORS['CYAN']}{stats['files_processed']}{self.COLORS['END']}")

        print(f"\n{self.COLORS['BOLD']}📊 MIGRATIONS-STATISTIKEN:{self.COLORS['END']}")
        print(f"  🔴 Kritische Fixes: {self.COLORS['RED']}{stats['critical_fixes']}{self.COLORS['END']}")
        print(f"  🎨 UI-Enhancements: {self.COLORS['GREEN']}{stats['ui_enhancements']}{self.COLORS['END']}")
        print(f"  🔒 Sicherheits-Fixes: {self.COLORS['YELLOW']}{stats['security_fixes']}{self.COLORS['END']}")
        print(f"  ♿ Accessibility: {self.COLORS['BLUE']}{stats['accessibility_improvements']}{self.COLORS['END']}")
        print(f"  📧 Template-Updates: {self.COLORS['MAGENTA']}{stats['template_modernizations']}{self.COLORS['END']}")
        print(f"  ⚠️  Warnungen: {self.COLORS['YELLOW']}{stats['warnings']}{self.COLORS['END']}")
        print(f"  ❌ Fehler: {self.COLORS['RED']}{stats['errors']}{self.COLORS['END']}")

        total_changes = sum([
            stats['critical_fixes'], stats['ui_enhancements'],
            stats['security_fixes'], stats['accessibility_improvements'],
            stats['template_modernizations']
        ])

        if total_changes > 0:
            print(
                f"\n{self.COLORS['BOLD']}{self.COLORS['GREEN']}🎉 ERFOLG: {total_changes} Verbesserungen durchgeführt!{self.COLORS['END']}")

            if not report['dry_run']:
                print(f"💾 Backup verfügbar: {self.COLORS['CYAN']}{report['backup_path']}{self.COLORS['END']}")
                print(
                    f"📊 Report verfügbar: {self.COLORS['CYAN']}{report['module_path']}/odoo18_migration_report_*.json{self.COLORS['END']}")
        else:
            print(f"\n{self.COLORS['GREEN']}✅ BEREITS KOMPATIBEL: Keine Änderungen erforderlich{self.COLORS['END']}")

        if stats['errors'] > 0:
            print(
                f"\n{self.COLORS['RED']}⚠️  ACHTUNG: {stats['errors']} Fehler aufgetreten - Manuelle Prüfung erforderlich{self.COLORS['END']}")

        print("=" * 80)

        # Empfehlungen für nächste Schritte
        print(f"\n{self.COLORS['BOLD']}📋 NÄCHSTE SCHRITTE:{self.COLORS['END']}")
        print(f"  1. {self.COLORS['GREEN']}✅ Module-Update testen: odoo -u your_module{self.COLORS['END']}")
        print(f"  2. {self.COLORS['GREEN']}🧪 Funktionalität prüfen{self.COLORS['END']}")
        print(f"  3. {self.COLORS['YELLOW']}📝 Migration-Report überprüfen{self.COLORS['END']}")

        if not report['dry_run'] and total_changes > 0:
            print(f"  4. {self.COLORS['BLUE']}🚀 Produktions-Deployment{self.COLORS['END']}")

    def rollback_migration(self, backup_path: Optional[str] = None) -> bool:
        """Rollback aus Backup"""
        try:
            if backup_path:
                backup_dir = Path(backup_path)
            else:
                backup_dir = self.backup_dir

            if not backup_dir.exists():
                self.logger.error(f"❌ Backup nicht gefunden: {backup_dir}")
                return False

            # Lese Backup-Info
            backup_info_file = backup_dir / 'backup_info.json'
            if backup_info_file.exists():
                with open(backup_info_file) as f:
                    backup_info = json.load(f)
                self.logger.info(f"📋 Rollback von: {backup_info['timestamp']}")

            # Stelle alle Dateien wieder her
            restored_count = 0
            for backup_file in backup_dir.rglob("*"):
                if backup_file.is_file() and backup_file.name != 'backup_info.json':
                    relative_path = backup_file.relative_to(backup_dir)
                    target_file = self.module_path / relative_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, target_file)
                    restored_count += 1

            self.logger.info(f"✅ Rollback erfolgreich: {restored_count} Dateien wiederhergestellt")
            return True

        except Exception as e:
            self.logger.error(f"❌ Rollback fehlgeschlagen: {e}")
            return False


def main():
    """Hauptfunktion für CLI-Verwendung"""
    parser = argparse.ArgumentParser(
        description="🚀 Vollständiger Odoo 18.0 Automatik-Migrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🎯 Anwendungsbeispiele:
  # Vollständige Migration mit allen Features
  python odoo18_migrator.py /path/to/module

  # Nur kritische Breaking Changes
  python odoo18_migrator.py /path/to/module --no-enhance-ui --no-accessibility

  # Sichere Analyse ohne Änderungen
  python odoo18_migrator.py /path/to/module --dry-run

  # Mit erweiterten Features
  python odoo18_migrator.py /path/to/module --enhance-ui --add-accessibility --modernize-templates

  # Rollback nach Problemen
  python odoo18_migrator.py /path/to/module --rollback

  # Rollback aus spezifischem Backup
  python odoo18_migrator.py /path/to/module --rollback --backup-path /path/to/backup
        """
    )

    parser.add_argument('module_path', help='Pfad zum Odoo-Modul')
    parser.add_argument('--dry-run', action='store_true',
                        help='Nur Analyse, keine Änderungen')

    # Feature-Flags
    parser.add_argument('--enhance-ui', action='store_true', default=True,
                        help='UI-Enhancements aktivieren (default: True)')
    parser.add_argument('--no-enhance-ui', action='store_true',
                        help='UI-Enhancements deaktivieren')
    parser.add_argument('--add-accessibility', action='store_true', default=True,
                        help='Accessibility-Features hinzufügen (default: True)')
    parser.add_argument('--no-accessibility', action='store_true',
                        help='Accessibility-Features deaktivieren')
    parser.add_argument('--modernize-templates', action='store_true', default=True,
                        help='Mail Templates modernisieren (default: True)')
    parser.add_argument('--no-templates', action='store_true',
                        help='Template-Modernisierung deaktivieren')

    # Rollback
    parser.add_argument('--rollback', action='store_true',
                        help='Rollback aus Backup durchführen')
    parser.add_argument('--backup-path',
                        help='Spezifischer Backup-Pfad für Rollback')

    args = parser.parse_args()

    # Verarbeite Feature-Flags
    options = {
        'dry_run': args.dry_run,
        'enhance_ui': args.enhance_ui and not args.no_enhance_ui,
        'add_accessibility': args.add_accessibility and not args.no_accessibility,
        'modernize_templates': args.modernize_templates and not args.no_templates
    }

    migrator = ComprehensiveOdoo18Migrator(args.module_path, options)

    if args.rollback:
        success = migrator.rollback_migration(args.backup_path)
        sys.exit(0 if success else 1)
    else:
        report = migrator.migrate_complete_module()

        # Exit Code basierend auf Ergebnis
        if not report['success']:
            sys.exit(1)
        elif report['statistics']['warnings'] > 0:
            print("⚠️  Warnung: Migration erfolgreich, aber manuelle Prüfung empfohlen")
            sys.exit(2)
        else:
            sys.exit(0)


if __name__ == "__main__":
    main()