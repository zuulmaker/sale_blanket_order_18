#!/usr/bin/env python3
"""
Odoo Module Encoding Fixer - Universal Tool
==========================================

Automatische Erkennung und Reparatur von Encoding-Problemen in Odoo-Modulen.

Usage:
    python3 odoo_encoding_fixer.py /path/to/your/module
    python3 odoo_encoding_fixer.py . 
    python3 odoo_encoding_fixer.py --help

Features:
- Automatische Encoding-Erkennung
- Backup vor Änderungen
- XML + Python Dateien Support
- Verifikation nach Fix
- Detailliertes Logging
- Fallback ohne externe Abhängigkeiten

Author: j.s.drees@az-zwick.com
License: AGPL-3.0
"""

import os
import sys
import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Optional dependencies
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

class Colors:
    """ANSI Color codes für Terminal-Output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

class OdooEncodingFixer:
    """Hauptklasse für Encoding-Fixes in Odoo-Modulen"""
    
    def __init__(self, module_path: str, create_backups: bool = True, verbose: bool = False):
        self.module_path = Path(module_path).resolve()
        self.create_backups = create_backups
        self.verbose = verbose
        
        # Statistiken
        self.stats = {
            'files_scanned': 0,
            'files_fixed': 0,
            'backups_created': 0,
            'errors': 0,
            'xml_files': 0,
            'python_files': 0
        }
        
        # Gefundene Probleme
        self.issues_found = []
        self.files_fixed = []
        
    def log(self, message: str, level: str = 'INFO', color: str = Colors.WHITE):
        """Logging mit Farben und Levels"""
        if level == 'DEBUG' and not self.verbose:
            return
            
        level_colors = {
            'ERROR': Colors.RED,
            'WARNING': Colors.YELLOW,
            'INFO': Colors.WHITE,
            'SUCCESS': Colors.GREEN,
            'DEBUG': Colors.CYAN
        }
        
        level_color = level_colors.get(level, Colors.WHITE)
        timestamp = ""  # Für einfacheren Output
        
        print(f"{level_color}{level:<7}{Colors.END} {color}{message}{Colors.END}")
    
    def validate_module_path(self) -> bool:
        """Validiert ob der Pfad ein Odoo-Modul ist"""
        if not self.module_path.exists():
            self.log(f"Path does not exist: {self.module_path}", 'ERROR', Colors.RED)
            return False
            
        if not self.module_path.is_dir():
            self.log(f"Path is not a directory: {self.module_path}", 'ERROR', Colors.RED)
            return False
        
        manifest_files = ['__manifest__.py', '__openerp__.py']
        has_manifest = any((self.module_path / manifest).exists() for manifest in manifest_files)
        
        if not has_manifest:
            self.log(f"No Odoo manifest found in: {self.module_path}", 'ERROR', Colors.RED)
            self.log("Expected: __manifest__.py or __openerp__.py", 'ERROR')
            return False
            
        self.log(f"✅ Valid Odoo module detected: {self.module_path.name}", 'SUCCESS', Colors.GREEN)
        return True
    
    def detect_encoding(self, file_path: Path) -> Tuple[str, float]:
        """Erkennt das Encoding einer Datei"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            
            if HAS_CHARDET:
                detected = chardet.detect(raw_data)
                encoding = detected.get('encoding', 'utf-8').lower()
                confidence = detected.get('confidence', 0.0)
            else:
                # Fallback-Erkennung ohne chardet
                try:
                    raw_data.decode('utf-8')
                    encoding = 'utf-8'
                    confidence = 0.9
                except UnicodeDecodeError:
                    try:
                        raw_data.decode('ascii')
                        encoding = 'ascii'
                        confidence = 0.8
                    except UnicodeDecodeError:
                        try:
                            raw_data.decode('latin-1')
                            encoding = 'latin-1'
                            confidence = 0.6
                        except UnicodeDecodeError:
                            encoding = 'unknown'
                            confidence = 0.0
            
            return encoding, confidence
            
        except Exception as e:
            self.log(f"Error detecting encoding for {file_path}: {e}", 'ERROR')
            return 'unknown', 0.0
    
    def read_file_content(self, file_path: Path, encoding: str) -> Optional[str]:
        """Liest Datei-Inhalt mit Fallback-Encodings"""
        encodings_to_try = [encoding, 'utf-8', 'latin-1', 'cp1252', 'ascii']
        
        for enc in encodings_to_try:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.read()
            except (UnicodeDecodeError, LookupError):
                continue
        
        self.log(f"Could not read {file_path} with any encoding", 'ERROR')
        return None
    
    def create_backup(self, file_path: Path) -> bool:
        """Erstellt Backup einer Datei"""
        if not self.create_backups:
            return True
            
        try:
            backup_path = file_path.with_suffix(file_path.suffix + '.encoding_backup')
            shutil.copy2(file_path, backup_path)
            self.stats['backups_created'] += 1
            self.log(f"📁 Backup created: {backup_path.name}", 'DEBUG')
            return True
        except Exception as e:
            self.log(f"Failed to create backup for {file_path}: {e}", 'ERROR')
            return False
    
    def fix_xml_encoding(self, file_path: Path) -> bool:
        """Repariert Encoding-Probleme in XML-Dateien"""
        encoding, confidence = self.detect_encoding(file_path)
        content = self.read_file_content(file_path, encoding)
        
        if content is None:
            return False
        
        needs_fix = False
        issues = []
        
        # Analysiere erste Zeile für XML-Deklaration
        lines = content.split('\n')
        first_line = lines[0].strip() if lines else ''
        
        # Prüfe auf XML-Deklaration
        if not first_line.startswith('<?xml'):
            needs_fix = True
            issues.append("Missing XML declaration")
        elif 'encoding=' not in first_line.lower():
            needs_fix = True
            issues.append("Missing encoding attribute in XML declaration")
        elif 'encoding="utf-8"' not in first_line.lower():
            needs_fix = True
            issues.append("Non-UTF-8 encoding declared")
        
        # Prüfe tatsächliches Encoding
        if encoding.lower() not in ['utf-8'] and 'utf-8' in first_line.lower():
            needs_fix = True
            issues.append(f"File encoding ({encoding}) doesn't match declaration (utf-8)")
        
        if not needs_fix:
            self.log(f"✅ {file_path.name}: Already correct", 'DEBUG')
            return True
        
        # Backup erstellen
        if not self.create_backup(file_path):
            return False
        
        # XML-Deklaration korrigieren
        if not first_line.startswith('<?xml'):
            # Füge XML-Deklaration hinzu
            content = '<?xml version="1.0" encoding="utf-8"?>\n' + content
        else:
            # Korrigiere existierende Deklaration
            corrected_line = '<?xml version="1.0" encoding="utf-8"?>'
            lines[0] = corrected_line
            content = '\n'.join(lines)
        
        try:
            # Schreibe als UTF-8
            with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)
            
            # Verifikation
            try:
                ET.parse(file_path)
                self.log(f"🔧 {file_path.name}: Fixed - {', '.join(issues)}", 'SUCCESS', Colors.GREEN)
                self.files_fixed.append(str(file_path))
                return True
            except ET.ParseError as e:
                self.log(f"❌ {file_path.name}: XML syntax error after fix: {e}", 'ERROR')
                return False
                
        except Exception as e:
            self.log(f"❌ {file_path.name}: Failed to write UTF-8: {e}", 'ERROR')
            return False
    
    def fix_python_encoding(self, file_path: Path) -> bool:
        """Repariert Encoding-Probleme in Python-Dateien"""
        encoding, confidence = self.detect_encoding(file_path)
        content = self.read_file_content(file_path, encoding)
        
        if content is None:
            return False
        
        needs_fix = False
        issues = []
        
        lines = content.split('\n')
        
        # Prüfe erste zwei Zeilen auf Encoding-Deklaration
        encoding_found = False
        for i in range(min(2, len(lines))):
            line = lines[i].strip()
            if 'coding:' in line or 'coding=' in line:
                encoding_found = True
                if 'utf-8' not in line.lower():
                    needs_fix = True
                    issues.append(f"Non-UTF-8 encoding in line {i+1}: {line}")
                break
        
        # Prüfe tatsächliches Encoding vs. Deklaration
        if encoding.lower() not in ['utf-8', 'ascii'] and encoding_found:
            needs_fix = True
            issues.append(f"File encoding ({encoding}) doesn't match UTF-8 declaration")
        
        if not encoding_found:
            # Nur bei non-ASCII Dateien Encoding-Header hinzufügen
            if encoding.lower() not in ['ascii', 'utf-8']:
                needs_fix = True
                issues.append("Non-ASCII file without encoding declaration")
        
        if not needs_fix:
            self.log(f"✅ {file_path.name}: Already correct", 'DEBUG')
            return True
        
        # Backup erstellen
        if not self.create_backup(file_path):
            return False
        
        # Encoding-Header hinzufügen falls nötig
        if not encoding_found and encoding.lower() not in ['ascii']:
            if lines and lines[0].startswith('#!'):
                # Shebang vorhanden - füge nach der ersten Zeile ein
                lines.insert(1, '# -*- coding: utf-8 -*-')
            else:
                # Füge am Anfang ein
                lines.insert(0, '# -*- coding: utf-8 -*-')
            content = '\n'.join(lines)
        
        try:
            # Schreibe als UTF-8
            with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)
            
            self.log(f"🔧 {file_path.name}: Fixed - {', '.join(issues)}", 'SUCCESS', Colors.GREEN)
            self.files_fixed.append(str(file_path))
            return True
            
        except Exception as e:
            self.log(f"❌ {file_path.name}: Failed to write UTF-8: {e}", 'ERROR')
            return False
    
    def scan_and_fix_files(self) -> bool:
        """Scannt und repariert alle relevanten Dateien im Modul"""
        
        # Dateimuster definieren
        file_patterns = {
            'xml': ['**/*.xml'],
            'python': ['**/*.py']
        }
        
        self.log("🔍 Scanning module for encoding issues...", 'INFO', Colors.CYAN)
        self.log(f"📁 Module path: {self.module_path}", 'INFO')
        
        if not HAS_CHARDET:
            self.log("⚠️ chardet not available - using fallback encoding detection", 'WARNING', Colors.YELLOW)
        
        success = True
        
        for file_type, patterns in file_patterns.items():
            files_found = []
            
            # Sammle alle Dateien für diesen Typ
            for pattern in patterns:
                files_found.extend(self.module_path.glob(pattern))
            
            if not files_found:
                continue
            
            self.log(f"\n📂 Processing {file_type.upper()} files ({len(files_found)} found):", 'INFO', Colors.MAGENTA)
            
            for file_path in sorted(files_found):
                self.stats['files_scanned'] += 1
                
                if file_type == 'xml':
                    self.stats['xml_files'] += 1
                    if self.fix_xml_encoding(file_path):
                        self.stats['files_fixed'] += 1
                    else:
                        success = False
                        self.stats['errors'] += 1
                        
                elif file_type == 'python':
                    self.stats['python_files'] += 1
                    if self.fix_python_encoding(file_path):
                        self.stats['files_fixed'] += 1
                    else:
                        success = False
                        self.stats['errors'] += 1
        
        return success
    
    def verify_fixes(self) -> bool:
        """Verifiziert alle Fixes"""
        self.log("\n🔍 Verifying fixes...", 'INFO', Colors.CYAN)
        
        verification_passed = True
        
        # Verifikation: Alle XML-Dateien
        xml_files = list(self.module_path.glob('**/*.xml'))
        xml_errors = []
        
        for xml_file in xml_files:
            try:
                ET.parse(xml_file)
                # Prüfe Encoding
                encoding, _ = self.detect_encoding(xml_file)
                if encoding.lower() not in ['utf-8', 'ascii']:
                    xml_errors.append(f"{xml_file.name}: Still {encoding} encoding")
            except ET.ParseError as e:
                xml_errors.append(f"{xml_file.name}: XML syntax error - {e}")
            except Exception as e:
                xml_errors.append(f"{xml_file.name}: Verification error - {e}")
        
        if xml_errors:
            verification_passed = False
            self.log("❌ XML verification failed:", 'ERROR', Colors.RED)
            for error in xml_errors:
                self.log(f"   - {error}", 'ERROR')
        else:
            self.log(f"✅ All {len(xml_files)} XML files verified successfully", 'SUCCESS', Colors.GREEN)
        
        # Verifikation: Encoding-Check
        all_files = list(self.module_path.glob('**/*.xml')) + list(self.module_path.glob('**/*.py'))
        encoding_issues = []
        
        for file_path in all_files:
            encoding, confidence = self.detect_encoding(file_path)
            if encoding.lower() not in ['utf-8', 'ascii']:
                encoding_issues.append(f"{file_path.name}: {encoding} (confidence: {confidence:.2f})")
        
        if encoding_issues:
            verification_passed = False
            self.log("❌ Encoding verification failed:", 'ERROR', Colors.RED)
            for issue in encoding_issues:
                self.log(f"   - {issue}", 'ERROR')
        else:
            self.log(f"✅ All files have correct UTF-8/ASCII encoding", 'SUCCESS', Colors.GREEN)
        
        return verification_passed
    
    def print_summary(self):
        """Druckt Zusammenfassung der Ergebnisse"""
        self.log("\n" + "="*60, 'INFO', Colors.BOLD)
        self.log("📊 ENCODING FIX SUMMARY", 'INFO', Colors.BOLD + Colors.UNDERLINE)
        self.log("="*60, 'INFO', Colors.BOLD)
        
        # Statistiken
        self.log(f"📁 Module: {Colors.BOLD}{self.module_path.name}{Colors.END}", 'INFO')
        self.log(f"📄 Files scanned: {self.stats['files_scanned']}", 'INFO')
        self.log(f"   - XML files: {self.stats['xml_files']}", 'INFO')
        self.log(f"   - Python files: {self.stats['python_files']}", 'INFO')
        self.log(f"🔧 Files fixed: {self.stats['files_fixed']}", 'SUCCESS' if self.stats['files_fixed'] > 0 else 'INFO')
        self.log(f"💾 Backups created: {self.stats['backups_created']}", 'INFO')
        self.log(f"❌ Errors: {self.stats['errors']}", 'ERROR' if self.stats['errors'] > 0 else 'INFO')
        
        # Reparierte Dateien
        if self.files_fixed:
            self.log(f"\n🔧 Files that were fixed:", 'INFO', Colors.YELLOW)
            for file_path in self.files_fixed:
                rel_path = Path(file_path).relative_to(self.module_path)
                self.log(f"   ✅ {rel_path}", 'SUCCESS', Colors.GREEN)
        
        # Empfehlungen
        self.log(f"\n💡 Next steps:", 'INFO', Colors.CYAN)
        if self.stats['files_fixed'] > 0:
            self.log("   1. Test Odoo module installation:", 'INFO')
            self.log(f"      odoo -d your_db -u {self.module_path.name} --stop-after-init", 'INFO', Colors.WHITE)
            self.log("   2. If successful, remove .encoding_backup files:", 'INFO')
            self.log(f"      find {self.module_path} -name '*.encoding_backup' -delete", 'INFO', Colors.WHITE)
        else:
            self.log("   ✅ No encoding issues found - module should install correctly", 'SUCCESS', Colors.GREEN)
    
    def run(self) -> bool:
        """Hauptmethode - führt kompletten Fix-Prozess aus"""
        self.log(f"🚀 Odoo Module Encoding Fixer v1.0", 'INFO', Colors.BOLD + Colors.CYAN)
        self.log(f"="*50, 'INFO', Colors.BOLD)
        
        # Validierung
        if not self.validate_module_path():
            return False
        
        # Scanning und Fixing
        fix_success = self.scan_and_fix_files()
        
        # Verifikation
        if fix_success:
            verify_success = self.verify_fixes()
        else:
            verify_success = False
        
        # Zusammenfassung
        self.print_summary()
        
        # Ergebnis
        if fix_success and verify_success:
            self.log(f"\n🎉 SUCCESS: Module encoding fixes completed successfully!", 'SUCCESS', Colors.BOLD + Colors.GREEN)
            return True
        else:
            self.log(f"\n💥 FAILURE: Some issues remain. Check the output above.", 'ERROR', Colors.BOLD + Colors.RED)
            return False

def main():
    """CLI Interface"""
    parser = argparse.ArgumentParser(
        description="Fix encoding issues in Odoo modules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/my_module          # Fix encoding in specific module
  %(prog)s .                          # Fix encoding in current directory
  %(prog)s . --no-backup              # Fix without creating backups
  %(prog)s . --verbose                # Verbose output
  %(prog)s . --no-backup --verbose    # Combined options

This tool will:
  - Detect encoding issues in XML and Python files
  - Create backups before making changes (unless --no-backup)
  - Fix XML declarations to use UTF-8
  - Add Python encoding headers where needed
  - Verify all fixes after completion
        """
    )
    
    parser.add_argument(
        'module_path',
        help='Path to the Odoo module directory'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backup files'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Odoo Encoding Fixer 1.0'
    )
    
    args = parser.parse_args()
    
    # Initialisiere Fixer
    fixer = OdooEncodingFixer(
        module_path=args.module_path,
        create_backups=not args.no_backup,
        verbose=args.verbose
    )
    
    # Führe Fix aus
    try:
        success = fixer.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        fixer.log("\n\n⚠️ Operation cancelled by user", 'WARNING', Colors.YELLOW)
        sys.exit(1)
    except Exception as e:
        fixer.log(f"\n💥 Unexpected error: {e}", 'ERROR', Colors.RED)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
