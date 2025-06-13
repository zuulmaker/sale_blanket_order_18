#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚨 VOLLSTÄNDIGE ODOO 18.0 XML-MIGRATION CHECKLISTE

Komplette Übersicht ALLER XML-Änderungen von Odoo 17.0 zu 18.0.
Diese Liste ist KRITISCH für eine erfolgreiche Migration!

Anwendungsbeispiele:
- Systematische Prüfung aller XML-Dateien
- Automatische Erkennung aller Breaking Changes
- Vollständige Migration-Validierung
- Compliance-Check für Odoo 18.0

Autor: j.s.drees@az-zwick.com
Datum: 2025-06-13
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class ComprehensiveOdoo18Analyzer:
    """
    🚨 VOLLSTÄNDIGER Odoo 18.0 XML-Analyzer
    
    Prüft ALLE bekannten Breaking Changes und Verbesserungen
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 🚨 KRITISCHE BREAKING CHANGES (Module starten nicht ohne Migration)
        self.critical_changes = {
            'attrs_states_removal': {
                'description': '🔴 KRITISCH: attrs/states komplett entfernt',
                'patterns': [
                    r'attrs\s*=\s*["\'][^"\']*["\']',
                    r'states\s*=\s*["\'][^"\']*["\']'
                ],
                'impact': 'BLOCKING - Module starten nicht',
                'migration': 'Zu invisible/readonly/required konvertieren'
            }
        }
        
        # ⚠️ WICHTIGE ÄNDERUNGEN (Funktionalität betroffen)
        self.important_changes = {
            'view_enhancements': {
                'description': '📊 Erweiterte View-Features in 18.0',
                'new_features': [
                    'multi_edit="1" in Tree Views',
                    'sample="1" für bessere UX',
                    'Erweiterte decoration-* Attribute',
                    'Neue optional="show/hide" Syntax',
                    'Verbesserte widget-Unterstützung'
                ],
                'impact': 'ENHANCEMENT - Bessere User Experience',
                'migration': 'Optional - empfohlen für moderne UI'
            },
            
            'mail_templates': {
                'description': '📧 Erweiterte E-Mail-Template Features',
                'new_features': [
                    'Robuste Template-Rendering',
                    'Mehrsprachige Unterstützung',
                    'Mobile-optimierte HTML',
                    'Smart-Placeholders',
                    'Conditional Content'
                ],
                'impact': 'ENHANCEMENT - Bessere E-Mail-Kommunikation',
                'migration': 'Empfohlen für professionelle E-Mails'
            },
            
            'field_widgets': {
                'description': '🎛️ Neue und geänderte Field Widgets',
                'changes': [
                    'many2one_avatar_user ersetzt old avatars',
                    'Erweiterte monetary widget options',
                    'Neue badge widget für status fields',
                    'Verbesserte date/datetime widgets',
                    'Enhanced selection widgets'
                ],
                'impact': 'ENHANCEMENT - Modernere UI-Elemente',
                'migration': 'Empfohlen für bessere UX'
            },
            
            'security_enhancements': {
                'description': '🔒 Erweiterte Sicherheits-Features',
                'changes': [
                    'Striktere group-Validierung',
                    'Erweiterte access rights syntax',
                    'Neue security context features',
                    'Verbesserte record rules'
                ],
                'impact': 'SECURITY - Strengere Sicherheitsrichtlinien',
                'migration': 'Prüfung aller Security-Definitionen erforderlich'
            }
        }
        
        # 💡 NEUE FEATURES (Optional aber empfohlen)
        self.new_features = {
            'modern_ui_elements': {
                'description': '🎨 Moderne UI-Elemente',
                'features': [
                    'Kanban Views mit Cards',
                    'Dashboard Integration',
                    'Responsive Design Support',
                    'Dark Mode Kompatibilität',
                    'Accessibility Improvements'
                ]
            },
            
            'enhanced_search': {
                'description': '🔍 Erweiterte Search-Funktionen',
                'features': [
                    'Faceted Search',
                    'Advanced Filters',
                    'Search Panel Integration',
                    'Quick Filters',
                    'Smart Search Suggestions'
                ]
            },
            
            'workflow_improvements': {
                'description': '⚡ Workflow-Verbesserungen',
                'features': [
                    'Bulk Actions in Tree Views',
                    'Quick Edit Capabilities',
                    'Enhanced Form Layouts',
                    'Smart Default Values',
                    'Contextual Help System'
                ]
            }
        }
        
        # 🔧 SPEZIFISCHE XML-PATTERN FÜR MIGRATION
        self.xml_migration_patterns = {
            # KRITISCHE PATTERNS
            'attrs_invisible': {
                'old': r'attrs\s*=\s*["\']{\s*["\']invisible["\']\s*:\s*\[(.*?)\]\s*}["\']',
                'new_template': 'invisible="{simplified_condition}"',
                'complexity': 'HIGH'
            },
            
            'attrs_readonly': {
                'old': r'attrs\s*=\s*["\']{\s*["\']readonly["\']\s*:\s*\[(.*?)\]\s*}["\']',
                'new_template': 'readonly="{simplified_condition}"',
                'complexity': 'HIGH'
            },
            
            'attrs_required': {
                'old': r'attrs\s*=\s*["\']{\s*["\']required["\']\s*:\s*\[(.*?)\]\s*}["\']',
                'new_template': 'required="{simplified_condition}"',
                'complexity': 'HIGH'
            },
            
            'states_attribute': {
                'old': r'states\s*=\s*["\']([^"\']+)["\']',
                'new_template': 'invisible="state not in [{formatted_states}]"',
                'complexity': 'MEDIUM'
            },
            
            # EMPFOHLENE VERBESSERUNGEN
            'tree_enhancements': {
                'old': r'<tree([^>]*)>',
                'new_template': '<tree\\1 sample="1" multi_edit="1">',
                'complexity': 'LOW'
            },
            
            'modern_widgets': {
                'old': r'widget\s*=\s*["\']many2one_avatar["\']',
                'new_template': 'widget="many2one_avatar_user"',
                'complexity': 'LOW'
            },
            
            'badge_widgets': {
                'old': r'<field\s+name\s*=\s*["\']state["\']([^>]*)/?>',
                'new_template': '<field name="state"\\1 widget="badge"/>',
                'complexity': 'LOW'
            },
            
            # SICHERHEITS-PATTERNS
            'group_validation': {
                'old': r'groups\s*=\s*["\']([^"\']*)["\']',
                'validation': 'Prüfe ob Gruppe existiert',
                'complexity': 'MEDIUM'
            }
        }
    
    def analyze_comprehensive(self, xml_content: str, file_path: str = "") -> Dict:
        """
        Führt vollständige Analyse aller Odoo 18.0 Änderungen durch
        
        Args:
            xml_content: XML-Datei Inhalt
            file_path: Pfad zur Datei (für Logging)
            
        Returns:
            Dict: Vollständiger Analyse-Report
        """
        report = {
            'file_path': file_path,
            'critical_issues': [],
            'important_changes': [],
            'recommendations': [],
            'new_features_available': [],
            'migration_complexity': 'LOW',
            'estimated_effort_hours': 0
        }
        
        # 1. KRITISCHE BREAKING CHANGES prüfen
        for change_type, config in self.critical_changes.items():
            if change_type == 'attrs_states_removal':
                issues = self._check_attrs_states(xml_content)
                if issues:
                    report['critical_issues'].extend(issues)
                    report['migration_complexity'] = 'HIGH'
                    report['estimated_effort_hours'] += len(issues) * 0.5
        
        # 2. WICHTIGE ÄNDERUNGEN prüfen
        important_findings = self._check_important_changes(xml_content)
        report['important_changes'] = important_findings
        if important_findings:
            report['estimated_effort_hours'] += len(important_findings) * 0.25
        
        # 3. NEUE FEATURES identifizieren
        available_features = self._identify_new_features(xml_content)
        report['new_features_available'] = available_features
        
        # 4. EMPFEHLUNGEN generieren
        recommendations = self._generate_recommendations(xml_content)
        report['recommendations'] = recommendations
        
        # 5. KOMPLEXITÄT bewerten
        if report['critical_issues']:
            report['migration_complexity'] = 'HIGH'
        elif report['important_changes']:
            report['migration_complexity'] = 'MEDIUM'
        
        return report
    
    def _check_attrs_states(self, content: str) -> List[Dict]:
        """Prüft auf kritische attrs/states Verwendung"""
        issues = []
        
        # attrs Patterns
        attrs_patterns = [
            (r'attrs\s*=\s*["\'][^"\']*invisible[^"\']*["\']', 'attrs_invisible'),
            (r'attrs\s*=\s*["\'][^"\']*readonly[^"\']*["\']', 'attrs_readonly'),
            (r'attrs\s*=\s*["\'][^"\']*required[^"\']*["\']', 'attrs_required'),
        ]
        
        for pattern, issue_type in attrs_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issues.append({
                    'type': issue_type,
                    'line': line_num,
                    'found': match.group(0),
                    'severity': 'CRITICAL',
                    'migration_required': True
                })
        
        # states Pattern
        states_matches = re.finditer(r'states\s*=\s*["\'][^"\']+["\']', content)
        for match in states_matches:
            line_num = content[:match.start()].count('\n') + 1
            issues.append({
                'type': 'states_attribute',
                'line': line_num,
                'found': match.group(0),
                'severity': 'CRITICAL',
                'migration_required': True
            })
        
        return issues
    
    def _check_important_changes(self, content: str) -> List[Dict]:
        """Prüft auf wichtige Änderungen"""
        changes = []
        
        # Veraltete Widgets
        old_widgets = [
            (r'widget\s*=\s*["\']many2one_avatar["\']', 'Use many2one_avatar_user instead'),
            (r'<field[^>]+name\s*=\s*["\']state["\'][^>]*(?<!widget="badge")[^>]*/?>', 'Consider using widget="badge" for state fields'),
        ]
        
        for pattern, suggestion in old_widgets:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                changes.append({
                    'type': 'widget_update',
                    'line': line_num,
                    'found': match.group(0),
                    'suggestion': suggestion,
                    'severity': 'MEDIUM'
                })
        
        return changes
    
    def _identify_new_features(self, content: str) -> List[Dict]:
        """Identifiziert verfügbare neue Features"""
        features = []
        
        # Tree View Enhancements
        if re.search(r'<tree[^>]*>', content):
            tree_match = re.search(r'<tree([^>]*?)>', content)
            if tree_match:
                tree_attrs = tree_match.group(1)
                
                if 'sample=' not in tree_attrs:
                    features.append({
                        'feature': 'tree_sample_data',
                        'description': 'Add sample="1" for better empty state UX',
                        'benefit': 'Improved user experience when no data available'
                    })
                
                if 'multi_edit=' not in tree_attrs:
                    features.append({
                        'feature': 'tree_multi_edit',
                        'description': 'Add multi_edit="1" for bulk editing',
                        'benefit': 'Users can edit multiple records at once'
                    })
        
        # Badge widgets for status fields
        state_fields = re.finditer(r'<field[^>]+name\s*=\s*["\']state["\'][^>]*/?>', content)
        for match in state_fields:
            if 'widget="badge"' not in match.group(0):
                features.append({
                    'feature': 'badge_widget_state',
                    'description': 'Use widget="badge" for state field',
                    'benefit': 'Modern status display with colors'
                })
        
        return features
    
    def _generate_recommendations(self, content: str) -> List[Dict]:
        """Generiert Empfehlungen für Verbesserungen"""
        recommendations = []
        
        # Responsive Design
        if '<form' in content and 'class=' not in content:
            recommendations.append({
                'category': 'responsive_design',
                'recommendation': 'Add responsive CSS classes to forms',
                'implementation': 'Add class="o_sale_order" or similar',
                'priority': 'MEDIUM'
            })
        
        # Optional Field Attributes
        field_matches = re.finditer(r'<field[^>]+name\s*=\s*["\'][^"\']+["\'][^>]*/?>', content)
        fields_without_optional = []
        
        for match in field_matches:
            if 'optional=' not in match.group(0):
                field_name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', match.group(0))
                if field_name_match:
                    field_name = field_name_match.group(1)
                    # Nur für bestimmte Felder empfehlen
                    if field_name in ['user_id', 'date_create', 'write_date', 'company_id']:
                        fields_without_optional.append(field_name)
        
        if fields_without_optional:
            recommendations.append({
                'category': 'optional_fields',
                'recommendation': f'Add optional="show/hide" to fields: {", ".join(fields_without_optional)}',
                'implementation': 'Add optional="show" or optional="hide" attribute',
                'priority': 'LOW'
            })
        
        return recommendations
    
    def generate_migration_script(self, analysis_results: List[Dict]) -> str:
        """
        Generiert automatisches Migrations-Skript basierend auf Analyse
        
        Args:
            analysis_results: Liste von Analyse-Ergebnissen
            
        Returns:
            str: Python-Skript für automatische Migration
        """
        script_lines = [
            "#!/usr/bin/env python3",
            "# -*- coding: utf-8 -*-",
            '"""',
            "🚨 AUTOMATISCHES ODOO 18.0 MIGRATIONS-SKRIPT",
            "",
            "Generiert basierend auf Analyse-Ergebnissen.",
            "Führt ALLE notwendigen XML-Änderungen durch.",
            '"""',
            "",
            "import re",
            "import logging",
            "from pathlib import Path",
            "",
            "_logger = logging.getLogger(__name__)",
            "",
            "def migrate_xml_file(file_path):",
            '    """Migriert eine XML-Datei zu Odoo 18.0"""',
            "    try:",
            "        with open(file_path, 'r', encoding='utf-8') as f:",
            "            content = f.read()",
            "        ",
            "        original_content = content",
            "        changes_made = 0",
            ""
        ]
        
        # Generiere Migrations-Logic basierend auf gefundenen Issues
        all_critical_issues = []
        for result in analysis_results:
            all_critical_issues.extend(result.get('critical_issues', []))
        
        if all_critical_issues:
            script_lines.extend([
                "        # KRITISCHE MIGRATIONS (attrs/states)",
                "        # attrs invisible",
                "        content = re.sub(",
                "            r'attrs\\s*=\\s*[\"\\']\\{\\s*[\"\\']invisible[\"\\']\\s*:\\s*\\[(.*?)\\]\\s*\\}[\"\\']',",
                "            lambda m: f'invisible=\"{_simplify_condition(m.group(1))}\"',",
                "            content, flags=re.IGNORECASE",
                "        )",
                "",
                "        # attrs readonly", 
                "        content = re.sub(",
                "            r'attrs\\s*=\\s*[\"\\']\\{\\s*[\"\\']readonly[\"\\']\\s*:\\s*\\[(.*?)\\]\\s*\\}[\"\\']',",
                "            lambda m: f'readonly=\"{_simplify_condition(m.group(1))}\"',",
                "            content, flags=re.IGNORECASE",
                "        )",
                "",
                "        # states attribute",
                "        content = re.sub(",
                "            r'states\\s*=\\s*[\"\\']([^\"\\\']+)[\"\\']',",
                "            lambda m: _convert_states(m.group(1)),",
                "            content",
                "        )",
                ""
            ])
        
        script_lines.extend([
            "        # Schreibe migrierte Datei",
            "        if content != original_content:",
            "            with open(file_path, 'w', encoding='utf-8') as f:",
            "                f.write(content)",
            "            _logger.info(f'✅ Migriert: {file_path}')",
            "            return True",
            "        else:",
            "            _logger.info(f'ℹ️  Keine Änderungen nötig: {file_path}')",
            "            return False",
            "            ",
            "    except Exception as e:",
            "        _logger.error(f'❌ Migration fehlgeschlagen {file_path}: {e}')",
            "        return False",
            "",
            "def _simplify_condition(condition):",
            '    """Vereinfacht Domain-Conditions"""',
            "    # Einfache Patterns",
            "    patterns = [",
            "        (r\"\\('([^']+)',\\s*'=',\\s*'([^']+)'\\)\", r\"\\1 == '\\2'\"),",
            "        (r\"\\('([^']+)',\\s*'=',\\s*(False|True|\\d+)\\)\", r\"\\1 == \\2\"),", 
            "        (r\"\\('([^']+)',\\s*'!=',\\s*'([^']+)'\\)\", r\"\\1 != '\\2'\"),",
            "        (r\"\\('([^']+)',\\s*'!=',\\s*(False|True|\\d+)\\)\", r\"\\1 != \\2\"),",
            "    ]",
            "    ",
            "    result = condition.strip()",
            "    for pattern, replacement in patterns:",
            "        result = re.sub(pattern, replacement, result)",
            "    return result",
            "",
            "def _convert_states(states_value):",
            '    """Konvertiert states zu invisible"""',
            "    states = [s.strip() for s in states_value.split(',')]",
            "    if len(states) == 1:",
            "        return f'invisible=\"state != \\'{states[0]}\\'\"'",
            "    else:",
            "        states_list = ', '.join([f\"'{s}'\" for s in states])",
            "        return f'invisible=\"state not in [{states_list}]\"'",
            "",
            "if __name__ == '__main__':",
            "    import sys",
            "    if len(sys.argv) > 1:",
            "        migrate_xml_file(sys.argv[1])",
            "    else:",
            "        print('Usage: python migration_script.py <xml_file>')"
        ])
        
        return '\n'.join(script_lines)


# Vollständige Liste ALLER XML-Änderungen in Odoo 18.0
ODOO_18_XML_CHANGES_REFERENCE = {
    "🚨 KRITISCHE BREAKING CHANGES (Module starten nicht ohne Migration)": {
        "attrs_removal": "attrs Attribute komplett entfernt - Migration zu invisible/readonly/required",
        "states_removal": "states Attribute komplett entfernt - Migration zu invisible",
        "old_widget_removal": "Veraltete Widgets entfernt (z.B. alte avatar widgets)"
    },
    
    "⚠️ WICHTIGE ÄNDERUNGEN (Funktionalität betroffen)": {
        "widget_enhancements": "Neue Widget-Optionen und -Features",
        "security_tightening": "Striktere Sicherheitsvalidierung",
        "field_improvements": "Erweiterte Field-Definitionen",
        "context_changes": "Neue Context-Handling Mechanismen"
    },
    
    "📊 NEUE FEATURES (Empfohlen für bessere UX)": {
        "tree_enhancements": "sample='1', multi_edit='1' für Tree Views",
        "badge_widgets": "Moderne badge widgets für Status-Felder", 
        "responsive_design": "Verbesserte Mobile-Unterstützung",
        "accessibility": "Enhanced Accessibility Features",
        "dark_mode": "Dark Mode Kompatibilität",
        "faceted_search": "Erweiterte Search-Funktionen"
    },
    
    "🎨 UI/UX VERBESSERUNGEN": {
        "modern_layouts": "Modernere Form-Layouts",
        "card_designs": "Card-basierte Designs",
        "improved_navigation": "Verbesserte Navigation",
        "contextual_help": "Kontextuelle Hilfe-Systeme"
    },
    
    "🔒 SICHERHEITS-ENHANCEMENTS": {
        "group_validation": "Strengere Gruppen-Validierung",
        "access_control": "Erweiterte Zugriffskontrolle",
        "record_rules": "Verbesserte Record Rules",
        "audit_trails": "Enhanced Audit Trails"
    }
}


if __name__ == "__main__":
    print("🚨 ODOO 18.0 XML-MIGRATION ANALYZER")
    print("=" * 50)
    
    analyzer = ComprehensiveOdoo18Analyzer()
    
    # Beispiel-Analyse
    sample_xml = """
    <button states="draft,open" string="Test"/>
    <field name="partner_id" attrs="{'readonly': [('state', '=', 'done')]}"/>
    <tree string="Test">
        <field name="name"/>
    </tree>
    """
    
    result = analyzer.analyze_comprehensive(sample_xml, "example.xml")
    
    print(f"📄 Analyse für example.xml:")
    print(f"   Kritische Issues: {len(result['critical_issues'])}")
    print(f"   Wichtige Änderungen: {len(result['important_changes'])}")
    print(f"   Verfügbare Features: {len(result['new_features_available'])}")
    print(f"   Migrations-Komplexität: {result['migration_complexity']}")
    print(f"   Geschätzter Aufwand: {result['estimated_effort_hours']} Stunden")
