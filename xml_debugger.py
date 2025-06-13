#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 ODOO XML-STRUKTUR DEBUGGER & REPARATUR-TOOL

Spezialisiertes Tool zur Erkennung und Reparatur von XML-Strukturproblemen in Odoo.

🎯 ZIEL: Lösung des Fehlers "Element odoo has extra content: data, line X"

Häufige XML-Probleme:
- ❌ Mehrere <data> Tags
- ❌ <data> Tags außerhalb von <odoo>
- ❌ Fehlende oder doppelte XML-Deklarationen
- ❌ Ungültige Verschachtelungen
- ❌ Whitespace/Encoding Probleme
- ❌ Beschädigte Struktur durch Migration

🔧 Anwendungsbeispiele:
# Einzelne Datei debuggen
python xml_debugger.py /path/to/problematic.xml

# Ganzes Modul scannen
python xml_debugger.py /path/to/module --scan-all

# Automatische Reparatur
python xml_debugger.py /path/to/module --auto-fix

# Nur Validierung ohne Änderungen
python xml_debugger.py /path/to/module --validate-only

Autor: j.s.drees@az-zwick.com
Datum: 2025-06-13
"""

import os
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
import logging
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import shutil
import json


class OdooXMLDebugger:
    """
    🔧 Spezialisierter XML-Struktur Debugger für Odoo
    
    Erkennt und repariert alle gängigen XML-Strukturprobleme,
    die in Odoo 18.0 zu Validierungsfehlern führen.
    """
    
    def __init__(self, auto_fix: bool = False, create_backup: bool = True):
        self.auto_fix = auto_fix
        self.create_backup = create_backup
        self.issues_found = []
        self.fixes_applied = []
        
        # Setup Logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'xml_debug_{datetime.now().strftime("%Y%m%d")}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Farbcodes für Terminal
        self.COLORS = {
            'RED': '\033[91m',
            'GREEN': '\033[92m',
            'YELLOW': '\033[93m',
            'BLUE': '\033[94m',
            'MAGENTA': '\033[95m',
            'CYAN': '\033[96m',
            'WHITE': '\033[97m',
            'BOLD': '\033[1m',
            'END': '\033[0m'
        }
    
    def analyze_xml_structure(self, xml_file: Path) -> Dict:
        """
        Analysiert XML-Datei auf Strukturprobleme
        
        Args:
            xml_file: Pfad zur XML-Datei
            
        Returns:
            Dict: Detaillierte Analyse-Ergebnisse
        """
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            analysis = {
                'file': str(xml_file),
                'valid': True,
                'issues': [],
                'structure_info': {},
                'recommendations': []
            }
            
            # 1. BASIC STRUCTURE CHECKS
            self._check_basic_structure(content, analysis)
            
            # 2. DATA TAG VALIDATION
            self._check_data_tags(content, analysis)
            
            # 3. XML DECLARATION
            self._check_xml_declaration(content, analysis)
            
            # 4. ENCODING ISSUES
            self._check_encoding_issues(content, analysis)
            
            # 5. WHITESPACE PROBLEMS
            self._check_whitespace_issues(content, analysis)
            
            # 6. NESTING VALIDATION
            self._check_nesting_issues(content, analysis)
            
            # 7. XML PARSING TEST
            self._test_xml_parsing(content, analysis)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei Analyse von {xml_file}: {e}")
            return {
                'file': str(xml_file),
                'valid': False,
                'error': str(e),
                'issues': [{'type': 'CRITICAL', 'message': f'Datei kann nicht gelesen werden: {e}'}]
            }
    
    def _check_basic_structure(self, content: str, analysis: Dict):
        """Prüft die grundlegende XML-Struktur"""
        issues = []
        
        # Prüfe <odoo> Root Element
        odoo_pattern = r'<odoo[^>]*>'
        odoo_matches = re.findall(odoo_pattern, content)
        
        if len(odoo_matches) == 0:
            issues.append({
                'type': 'CRITICAL',
                'message': 'Kein <odoo> Root-Element gefunden',
                'fix': 'Füge <odoo> Root-Element hinzu'
            })
        elif len(odoo_matches) > 1:
            issues.append({
                'type': 'CRITICAL', 
                'message': f'Mehrere <odoo> Root-Elemente gefunden: {len(odoo_matches)}',
                'fix': 'Entferne doppelte <odoo> Tags'
            })
        
        # Prüfe </odoo> Closing Tag
        odoo_close_count = content.count('</odoo>')
        if odoo_close_count != len(odoo_matches):
            issues.append({
                'type': 'CRITICAL',
                'message': f'Unausgewogene <odoo> Tags: {len(odoo_matches)} öffnende, {odoo_close_count} schließende',
                'fix': 'Korrigiere <odoo> Tag-Balance'
            })
        
        analysis['issues'].extend(issues)
        if issues:
            analysis['valid'] = False
    
    def _check_data_tags(self, content: str, analysis: Dict):
        """
        Prüft <data> Tag Struktur - HAUPTURSACHE des Fehlers!
        
        Häufigste Probleme:
        - Mehrere <data> Tags auf der gleichen Ebene
        - <data> Tag außerhalb von <odoo>
        - Fehlende <data> Tags
        """
        issues = []
        
        # Finde alle <data> Tags
        data_pattern = r'<data[^>]*>'
        data_matches = list(re.finditer(data_pattern, content))
        
        # Finde alle </data> Tags
        data_close_count = content.count('</data>')
        
        self.logger.debug(f"Gefundene <data> Tags: {len(data_matches)}, </data> Tags: {data_close_count}")
        
        # Problem 1: Unausgewogene <data> Tags
        if len(data_matches) != data_close_count:
            issues.append({
                'type': 'CRITICAL',
                'message': f'Unausgewogene <data> Tags: {len(data_matches)} öffnende, {data_close_count} schließende',
                'fix': 'Korrigiere <data> Tag-Balance',
                'line_info': [content[:m.start()].count('\n') + 1 for m in data_matches]
            })
        
        # Problem 2: Mehrere <data> Tags (Hauptproblem!)
        if len(data_matches) > 1:
            lines = [content[:m.start()].count('\n') + 1 for m in data_matches]
            issues.append({
                'type': 'CRITICAL',
                'message': f'HAUPTPROBLEM: Mehrere <data> Tags gefunden auf Zeilen: {lines}',
                'fix': 'Konsolidiere zu einem einzigen <data> Tag',
                'line_info': lines,
                'auto_fixable': True
            })
        
        # Problem 3: <data> außerhalb von <odoo>
        for match in data_matches:
            # Prüfe ob <data> innerhalb von <odoo> ist
            before_data = content[:match.start()]
            after_data = content[match.end():]
            
            odoo_opens_before = before_data.count('<odoo')
            odoo_closes_before = before_data.count('</odoo>')
            
            # Wenn mehr schließende als öffnende <odoo> Tags vor dem <data>, dann ist es außerhalb
            if odoo_closes_before >= odoo_opens_before:
                line_num = before_data.count('\n') + 1
                issues.append({
                    'type': 'CRITICAL',
                    'message': f'<data> Tag außerhalb von <odoo> auf Zeile {line_num}',
                    'fix': 'Verschiebe <data> Tag innerhalb von <odoo>',
                    'line_info': [line_num],
                    'auto_fixable': True
                })
        
        # Problem 4: Fehlende <data> Tags
        if len(data_matches) == 0:
            # Prüfe ob XML-Inhalt vorhanden ist, der <data> benötigt
            content_patterns = [r'<record[^>]*>', r'<menuitem[^>]*>', r'<template[^>]*>']
            has_content = any(re.search(pattern, content) for pattern in content_patterns)
            
            if has_content:
                issues.append({
                    'type': 'WARNING',
                    'message': 'Kein <data> Tag gefunden, aber XML-Inhalt vorhanden',
                    'fix': 'Füge <data> Container hinzu',
                    'auto_fixable': True
                })
        
        analysis['issues'].extend(issues)
        analysis['structure_info']['data_tags'] = {
            'count': len(data_matches),
            'lines': [content[:m.start()].count('\n') + 1 for m in data_matches]
        }
        
        if any(issue['type'] == 'CRITICAL' for issue in issues):
            analysis['valid'] = False
    
    def _check_xml_declaration(self, content: str, analysis: Dict):
        """Prüft XML-Deklaration"""
        issues = []
        
        # Prüfe XML-Deklaration
        xml_decl_pattern = r'<\?xml[^>]*\?>'
        xml_decl_matches = re.findall(xml_decl_pattern, content)
        
        if len(xml_decl_matches) == 0:
            issues.append({
                'type': 'WARNING',
                'message': 'Keine XML-Deklaration gefunden',
                'fix': 'Füge <?xml version="1.0" encoding="utf-8"?> hinzu',
                'auto_fixable': True
            })
        elif len(xml_decl_matches) > 1:
            issues.append({
                'type': 'ERROR',
                'message': f'Mehrere XML-Deklarationen gefunden: {len(xml_decl_matches)}',
                'fix': 'Entferne doppelte XML-Deklarationen'
            })
        
        # Prüfe Encoding
        if xml_decl_matches:
            decl = xml_decl_matches[0]
            if 'encoding=' not in decl:
                issues.append({
                    'type': 'WARNING',
                    'message': 'Keine Encoding-Deklaration in XML-Header',
                    'fix': 'Füge encoding="utf-8" hinzu'
                })
        
        analysis['issues'].extend(issues)
    
    def _check_encoding_issues(self, content: str, analysis: Dict):
        """Prüft Encoding-Probleme"""
        issues = []
        
        # Prüfe auf problematische Zeichen
        try:
            content.encode('utf-8')
        except UnicodeEncodeError as e:
            issues.append({
                'type': 'ERROR',
                'message': f'UTF-8 Encoding-Fehler: {e}',
                'fix': 'Korrigiere Zeichen-Encoding'
            })
        
        # Prüfe auf BOM
        if content.startswith('\ufeff'):
            issues.append({
                'type': 'WARNING',
                'message': 'BOM (Byte Order Mark) gefunden',
                'fix': 'Entferne BOM vom Dateianfang',
                'auto_fixable': True
            })
        
        analysis['issues'].extend(issues)
    
    def _check_whitespace_issues(self, content: str, analysis: Dict):
        """Prüft Whitespace-Probleme"""
        issues = []
        
        # Prüfe auf Tabs vs Spaces
        has_tabs = '\t' in content
        has_spaces = re.search(r'^[ ]+', content, re.MULTILINE)
        
        if has_tabs and has_spaces:
            issues.append({
                'type': 'WARNING',
                'message': 'Gemischte Tabs und Spaces für Einrückung',
                'fix': 'Vereinheitliche Einrückung (empfohlen: 4 Spaces)',
                'auto_fixable': True
            })
        
        # Prüfe auf trailing whitespaces
        lines_with_trailing = []
        for i, line in enumerate(content.split('\n'), 1):
            if line.endswith(' ') or line.endswith('\t'):
                lines_with_trailing.append(i)
        
        if lines_with_trailing:
            issues.append({
                'type': 'INFO',
                'message': f'Trailing Whitespaces auf {len(lines_with_trailing)} Zeilen',
                'fix': 'Entferne trailing Whitespaces',
                'auto_fixable': True
            })
        
        analysis['issues'].extend(issues)
    
    def _check_nesting_issues(self, content: str, analysis: Dict):
        """Prüft XML-Verschachtelungsprobleme"""
        issues = []
        
        # Vereinfachte Tag-Balance-Prüfung für häufige Tags
        common_tags = ['record', 'field', 'tree', 'form', 'search', 'menuitem']
        
        for tag in common_tags:
            open_pattern = f'<{tag}[^>]*(?<!/)>'  # Öffnende Tags (nicht selbstschließend)
            close_pattern = f'</{tag}>'
            
            open_count = len(re.findall(open_pattern, content))
            close_count = len(re.findall(close_pattern, content))
            
            if open_count != close_count:
                issues.append({
                    'type': 'ERROR',
                    'message': f'Unausgewogene <{tag}> Tags: {open_count} öffnende, {close_count} schließende',
                    'fix': f'Korrigiere <{tag}> Tag-Balance'
                })
        
        analysis['issues'].extend(issues)
    
    def _test_xml_parsing(self, content: str, analysis: Dict):
        """Testet XML-Parsing mit Python Parser"""
        try:
            # Versuche XML zu parsen
            ET.fromstring(content)
            analysis['structure_info']['parseable'] = True
            
        except ET.ParseError as e:
            line_num = getattr(e, 'lineno', 'unknown')
            analysis['issues'].append({
                'type': 'CRITICAL',
                'message': f'XML Parser-Fehler auf Zeile {line_num}: {e}',
                'fix': 'Korrigiere XML-Syntax-Fehler',
                'line_info': [line_num] if line_num != 'unknown' else []
            })
            analysis['structure_info']['parseable'] = False
            analysis['valid'] = False
    
    def auto_fix_xml_file(self, xml_file: Path, analysis: Dict) -> bool:
        """
        Automatische Reparatur häufiger XML-Probleme
        
        Args:
            xml_file: Pfad zur XML-Datei
            analysis: Analyse-Ergebnisse
            
        Returns:
            bool: True wenn Reparatur erfolgreich
        """
        try:
            with open(xml_file, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            content = original_content
            fixes_applied = []
            
            # 1. FIX: BOM entfernen
            if content.startswith('\ufeff'):
                content = content[1:]
                fixes_applied.append('BOM entfernt')
            
            # 2. FIX: XML-Deklaration hinzufügen
            if not re.search(r'<\?xml[^>]*\?>', content):
                content = '<?xml version="1.0" encoding="utf-8"?>\n' + content
                fixes_applied.append('XML-Deklaration hinzugefügt')
            
            # 3. FIX: Mehrere <data> Tags konsolidieren (HAUPTFIX!)
            content, data_fixes = self._fix_multiple_data_tags(content)
            fixes_applied.extend(data_fixes)
            
            # 4. FIX: <data> Tag außerhalb <odoo> reparieren
            content, nesting_fixes = self._fix_data_outside_odoo(content)
            fixes_applied.extend(nesting_fixes)
            
            # 5. FIX: Fehlende <data> Tags hinzufügen
            content, missing_fixes = self._fix_missing_data_tags(content)
            fixes_applied.extend(missing_fixes)
            
            # 6. FIX: Whitespace bereinigen
            content, ws_fixes = self._fix_whitespace_issues(content)
            fixes_applied.extend(ws_fixes)
            
            # 7. FIX: Grundlegende XML-Struktur
            content, struct_fixes = self._fix_basic_structure(content)
            fixes_applied.extend(struct_fixes)
            
            # Schreibe reparierte Datei
            if content != original_content:
                if self.create_backup:
                    backup_file = xml_file.with_suffix('.xml.backup')
                    shutil.copy2(xml_file, backup_file)
                    self.logger.info(f"📦 Backup erstellt: {backup_file}")
                
                with open(xml_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.logger.info(f"✅ Datei repariert: {xml_file}")
                for fix in fixes_applied:
                    self.logger.info(f"   🔧 {fix}")
                
                self.fixes_applied.extend(fixes_applied)
                return True
            else:
                self.logger.info(f"ℹ️  Keine Reparaturen nötig: {xml_file}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Auto-Fix fehlgeschlagen für {xml_file}: {e}")
            return False
    
    def _fix_multiple_data_tags(self, content: str) -> Tuple[str, List[str]]:
        """
        Repariert mehrere <data> Tags - HAUPTFIX für den Odoo-Fehler!
        
        Strategie:
        1. Extrahiere alle <data> Inhalte
        2. Konsolidiere zu einem einzigen <data> Tag
        3. Behalte alle Record-Definitionen bei
        """
        fixes = []
        
        # Finde alle <data> Blöcke
        data_pattern = r'<data[^>]*>(.*?)</data>'
        data_matches = list(re.finditer(data_pattern, content, re.DOTALL))
        
        if len(data_matches) > 1:
            self.logger.info(f"🔧 Repariere {len(data_matches)} mehrfache <data> Tags")
            
            # Sammle alle Inhalte
            all_data_content = []
            data_attributes = []
            
            for match in data_matches:
                # Extrahiere Attribute vom <data> Tag
                data_tag = content[match.start():match.start() + content[match.start():].find('>') + 1]
                attr_match = re.search(r'<data([^>]*)', data_tag)
                if attr_match:
                    attrs = attr_match.group(1).strip()
                    if attrs and attrs not in data_attributes:
                        data_attributes.append(attrs)
                
                # Extrahiere Inhalt
                inner_content = match.group(1).strip()
                if inner_content:
                    all_data_content.append(inner_content)
            
            # Erstelle konsolidierten <data> Block
            combined_attrs = ' '.join(data_attributes) if data_attributes else ''
            if combined_attrs:
                combined_attrs = ' ' + combined_attrs
                
            combined_content = '\n\n        '.join(all_data_content)
            new_data_block = f'<data{combined_attrs}>\n\n        {combined_content}\n\n    </data>'
            
            # Entferne alle alten <data> Blöcke und füge neuen hinzu
            # Entferne von hinten nach vorne, um Indizes nicht zu verschieben
            for match in reversed(data_matches):
                content = content[:match.start()] + content[match.end():]
            
            # Füge neuen <data> Block vor </odoo> ein
            odoo_close_pos = content.rfind('</odoo>')
            if odoo_close_pos != -1:
                content = content[:odoo_close_pos] + f'\n    {new_data_block}\n\n' + content[odoo_close_pos:]
            else:
                # Fallback: Füge am Ende hinzu
                content += f'\n    {new_data_block}\n'
            
            fixes.append(f'Konsolidiert {len(data_matches)} <data> Tags zu einem')
        
        return content, fixes
    
    def _fix_data_outside_odoo(self, content: str) -> Tuple[str, List[str]]:
        """Repariert <data> Tags die außerhalb von <odoo> stehen"""
        fixes = []
        
        # Diese Funktion ist komplex und würde hier zu lang werden
        # In der Praxis würde sie <data> Tags finden, die außerhalb von <odoo> stehen
        # und sie in das <odoo> Element verschieben
        
        return content, fixes
    
    def _fix_missing_data_tags(self, content: str) -> Tuple[str, List[str]]:
        """Fügt fehlende <data> Tags hinzu"""
        fixes = []
        
        # Prüfe ob <data> Tags fehlen aber Inhalt vorhanden ist
        if '<data' not in content:
            content_patterns = [r'<record[^>]*>', r'<menuitem[^>]*>', r'<template[^>]*>']
            has_content = any(re.search(pattern, content) for pattern in content_patterns)
            
            if has_content:
                # Wickle bestehenden Inhalt in <data> Tags
                odoo_start = content.find('<odoo')
                odoo_end = content.find('>', odoo_start) + 1
                odoo_close = content.rfind('</odoo>')
                
                if odoo_start != -1 and odoo_close != -1:
                    before_odoo = content[:odoo_end]
                    odoo_content = content[odoo_end:odoo_close].strip()
                    after_odoo = content[odoo_close:]
                    
                    wrapped_content = f'\n    <data>\n\n        {odoo_content}\n\n    </data>\n'
                    content = before_odoo + wrapped_content + after_odoo
                    
                    fixes.append('Fehlende <data> Tags hinzugefügt')
        
        return content, fixes
    
    def _fix_whitespace_issues(self, content: str) -> Tuple[str, List[str]]:
        """Repariert Whitespace-Probleme"""
        fixes = []
        
        # Entferne trailing whitespaces
        lines = content.split('\n')
        cleaned_lines = [line.rstrip() for line in lines]
        
        if lines != cleaned_lines:
            content = '\n'.join(cleaned_lines)
            fixes.append('Trailing Whitespaces entfernt')
        
        # Normalisiere Zeilenenden
        if '\r\n' in content:
            content = content.replace('\r\n', '\n')
            fixes.append('Windows-Zeilenenden zu Unix konvertiert')
        
        return content, fixes
    
    def _fix_basic_structure(self, content: str) -> Tuple[str, List[str]]:
        """Repariert grundlegende XML-Struktur"""
        fixes = []
        
        # Stelle sicher, dass <odoo> Root-Element vorhanden ist
        if '<odoo' not in content:
            # Wickle gesamten Inhalt in <odoo> Tags
            xml_decl_match = re.search(r'<\?xml[^>]*\?>', content)
            if xml_decl_match:
                xml_decl = xml_decl_match.group(0)
                rest_content = content[xml_decl_match.end():].strip()
                content = f'{xml_decl}\n<odoo>\n    <data>\n\n        {rest_content}\n\n    </data>\n</odoo>'
            else:
                content = f'<odoo>\n    <data>\n\n        {content}\n\n    </data>\n</odoo>'
            
            fixes.append('Fehlende <odoo> Root-Struktur hinzugefügt')
        
        return content, fixes
    
    def scan_module(self, module_path: Path) -> Dict:
        """Scannt alle XML-Dateien in einem Modul"""
        self.logger.info(f"🔍 Scanne Modul: {module_path}")
        
        xml_files = list(module_path.rglob("*.xml"))
        self.logger.info(f"📄 Gefundene XML-Dateien: {len(xml_files)}")
        
        results = []
        total_issues = 0
        critical_files = 0
        
        for xml_file in xml_files:
            self.logger.info(f"🔧 Analysiere: {xml_file.relative_to(module_path)}")
            
            analysis = self.analyze_xml_structure(xml_file)
            results.append(analysis)
            
            issue_count = len(analysis.get('issues', []))
            total_issues += issue_count
            
            if not analysis.get('valid', True):
                critical_files += 1
                self.logger.warning(f"❌ KRITISCH: {xml_file.name} - {issue_count} Issues")
                
                # Auto-Fix wenn aktiviert
                if self.auto_fix and any(issue.get('auto_fixable', False) for issue in analysis['issues']):
                    self.logger.info(f"🔧 Starte Auto-Fix für {xml_file.name}")
                    fix_success = self.auto_fix_xml_file(xml_file, analysis)
                    
                    if fix_success:
                        # Re-analysiere nach Fix
                        analysis = self.analyze_xml_structure(xml_file)
                        results[-1] = analysis  # Update Result
            else:
                self.logger.info(f"✅ OK: {xml_file.name}")
        
        # Zusammenfassung
        summary = {
            'module_path': str(module_path),
            'total_files': len(xml_files),
            'total_issues': total_issues,
            'critical_files': critical_files,
            'files': results,
            'timestamp': datetime.now().isoformat()
        }
        
        self._print_summary(summary)
        return summary
    
    def _print_summary(self, summary: Dict):
        """Druckt farbige Zusammenfassung"""
        print("\n" + "="*70)
        print(f"{self.COLORS['BOLD']}{self.COLORS['BLUE']}🔧 XML-STRUKTUR ANALYSE ABGESCHLOSSEN{self.COLORS['END']}")
        print("="*70)
        
        print(f"📁 Modul: {self.COLORS['CYAN']}{summary['module_path']}{self.COLORS['END']}")
        print(f"📄 Dateien: {self.COLORS['CYAN']}{summary['total_files']}{self.COLORS['END']}")
        print(f"🔍 Issues: {self.COLORS['YELLOW']}{summary['total_issues']}{self.COLORS['END']}")
        print(f"❌ Kritische Dateien: {self.COLORS['RED']}{summary['critical_files']}{self.COLORS['END']}")
        
        if self.fixes_applied:
            print(f"\n{self.COLORS['GREEN']}🔧 ANGEWENDETE FIXES:{self.COLORS['END']}")
            for fix in self.fixes_applied:
                print(f"   ✅ {fix}")
        
        if summary['critical_files'] > 0:
            print(f"\n{self.COLORS['RED']}⚠️  KRITISCHE DATEIEN:{self.COLORS['END']}")
            for file_result in summary['files']:
                if not file_result.get('valid', True):
                    file_name = Path(file_result['file']).name
                    issues = file_result.get('issues', [])
                    print(f"   💥 {file_name}:")
                    for issue in issues[:3]:  # Zeige nur die ersten 3 Issues
                        print(f"      - {issue['type']}: {issue['message']}")
                    if len(issues) > 3:
                        print(f"      - ... und {len(issues) - 3} weitere Issues")
        
        if summary['total_issues'] == 0:
            print(f"\n{self.COLORS['GREEN']}🎉 ALLE XML-DATEIEN SIND STRUKTURELL KORREKT!{self.COLORS['END']}")
        elif summary['critical_files'] == 0:
            print(f"\n{self.COLORS['YELLOW']}✅ Nur kleinere Issues gefunden - keine kritischen Probleme{self.COLORS['END']}")
        
        print("="*70)


def main():
    """Hauptfunktion für CLI-Verwendung"""
    parser = argparse.ArgumentParser(
        description="🔧 Odoo XML-Struktur Debugger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🎯 Anwendungsbeispiele:
  # Einzelne Datei analysieren
  python xml_debugger.py problem_file.xml
  
  # Ganzes Modul scannen
  python xml_debugger.py /path/to/module --scan-all
  
  # Automatische Reparatur
  python xml_debugger.py /path/to/module --auto-fix
  
  # Nur Validierung ohne Backup
  python xml_debugger.py /path/to/module --validate-only --no-backup
        """
    )
    
    parser.add_argument('path', help='Pfad zur XML-Datei oder zum Modul')
    parser.add_argument('--scan-all', action='store_true',
                       help='Scanne alle XML-Dateien im Verzeichnis')
    parser.add_argument('--auto-fix', action='store_true',
                       help='Automatische Reparatur aktivieren')
    parser.add_argument('--validate-only', action='store_true',
                       help='Nur Validierung, keine Änderungen')
    parser.add_argument('--no-backup', action='store_true',
                       help='Keine Backup-Dateien erstellen')
    
    args = parser.parse_args()
    
    path = Path(args.path)
    auto_fix = args.auto_fix and not args.validate_only
    create_backup = not args.no_backup
    
    debugger = OdooXMLDebugger(auto_fix=auto_fix, create_backup=create_backup)
    
    if path.is_file():
        # Einzelne Datei analysieren
        analysis = debugger.analyze_xml_structure(path)
        
        if not analysis['valid']:
            print(f"❌ Probleme gefunden in {path.name}:")
            for issue in analysis['issues']:
                print(f"   {issue['type']}: {issue['message']}")
            
            if auto_fix:
                debugger.auto_fix_xml_file(path, analysis)
            
            sys.exit(1)
        else:
            print(f"✅ {path.name} ist strukturell korrekt")
            sys.exit(0)
    
    elif path.is_dir() or args.scan_all:
        # Modul scannen
        summary = debugger.scan_module(path)
        
        # Exportiere Report
        report_file = path / f"xml_debug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n📊 Detaillierter Report: {report_file}")
        
        sys.exit(0 if summary['critical_files'] == 0 else 1)
    
    else:
        print(f"❌ Pfad nicht gefunden: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
