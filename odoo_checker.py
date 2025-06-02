#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Optional

# Konfiguration - Diese Variablen können angepasst werden
LICENSE_HEADER = """# -*- coding: utf-8 -*-
# Copyright {year} {author}
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# Date: {creation_date}
# Authors: J.s.drees@az-zwick.com & kd.gundermann@az-zwick.com
"""

AUTHOR = "j.s.drees@az-zwick.com & kd.gundermann@az-zwick.com"
CURRENT_YEAR = datetime.now().year

# Dateierweiterungen die einen Header bekommen sollen
HEADER_EXTENSIONS = {'.py', '.xml', '.js', '.scss', '.css'}

# Ordner die ignoriert werden sollen
IGNORE_FOLDERS = {'static', 'wizard', '__pycache__', '.git', '.vscode', 'migrations'}

# Odoo Core Module (diese werden nicht umbenannt)
ODOO_CORE_MODULES = {
    'base', 'web', 'mail', 'account', 'sale', 'purchase', 'stock', 
    'hr', 'project', 'website', 'portal', 'payment', 'delivery'
}

class OdooModuleChecker:
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path).resolve()
        self.errors = []
        self.warnings = []
        self.changes_made = []
        self.module_name = None
        
    def log_error(self, message: str):
        """Fehlertolerant: Sammelt Fehler statt zu crashen"""
        self.errors.append(f"FEHLER: {message}")
        print(f"❌ {message}")
    
    def log_warning(self, message: str):
        """Warnung ausgeben"""
        self.warnings.append(f"WARNUNG: {message}")
        print(f"⚠️  {message}")
    
    def log_change(self, message: str):
        """Änderung protokollieren"""
        self.changes_made.append(message)
        print(f"✅ {message}")

    def is_custom_module_directory(self) -> bool:
        """Prüft ob der aktuelle Arbeitsordner ein eigenes Modul ist (zw_ Präfix)"""
        folder_name = self.base_path.name
        return folder_name.startswith('zw_') and folder_name not in ODOO_CORE_MODULES

    def get_module_name(self) -> Optional[str]:
        """Extrahiert den Modulnamen aus dem aktuellen Arbeitsordner"""
        if self.is_custom_module_directory():
            return self.base_path.name[3:]  # Entfernt "zw_" Präfix
        return None

    def should_ignore_folder(self, folder_name: str) -> bool:
        """Prüft ob ein Ordner ignoriert werden soll"""
        return folder_name in IGNORE_FOLDERS or folder_name.startswith('.')

    def get_file_creation_date(self, file_path: Path) -> str:
        """Ermittelt das Erstellungsdatum einer Datei (fehlertolerant)"""
        try:
            # Versuche Erstellungsdatum zu ermitteln
            stat = file_path.stat()
            
            # Auf Windows: st_ctime ist Erstellungszeit
            # Auf Unix/Linux: st_ctime ist letzte Metadaten-Änderung
            # Als Fallback verwenden wir das ältere von beiden Daten
            creation_time = min(stat.st_ctime, stat.st_mtime)
            
            # In lesbares Datum umwandeln
            creation_date = datetime.fromtimestamp(creation_time)
            return creation_date.strftime("%Y-%m-%d")
            
        except Exception as e:
            self.log_warning(f"Konnte Erstellungsdatum für {file_path} nicht ermitteln: {e}")
            # Fallback: aktuelles Datum
            return datetime.now().strftime("%Y-%m-%d")

    def generate_header(self, file_path: Path) -> str:
        """Generiert den passenden Header basierend auf Dateierweiterung und Erstellungsdatum"""
        file_extension = file_path.suffix.lower()
        creation_date = self.get_file_creation_date(file_path)
        
        header = LICENSE_HEADER.format(
            year=CURRENT_YEAR, 
            author=AUTHOR,
            creation_date=creation_date
        )
        
        if file_extension == '.xml':
            return f'<?xml version="1.0" encoding="utf-8"?>\n<!--\n{header}\n-->\n'
        elif file_extension in {'.js', '.scss', '.css'}:
            return f'/*\n{header}\n*/\n'
        else:  # Python und andere
            return f'{header}\n'

    def has_license_header(self, content: str, file_extension: str) -> bool:
        """Prüft idempotent ob bereits ein Lizenz-Header vorhanden ist"""
        header_indicators = ['License AGPL-3.0', 'Copyright', 'Created:']
        
        if file_extension == '.xml':
            return any(indicator in content[:500] for indicator in header_indicators)
        elif file_extension in {'.js', '.scss', '.css'}:
            return any(indicator in content[:500] for indicator in header_indicators)
        else:  # Python
            return (any(indicator in content[:500] for indicator in header_indicators) or
                   '# -*- coding: utf-8 -*-' in content[:100])

    def check_file_naming(self, file_path: Path, module_name: str) -> bool:
        """Prüft ob Dateiname dem Modul entspricht (nur für relevante Dateien)"""
        file_name = file_path.stem
        
        # Spezielle Dateien die nicht umbenannt werden
        special_files = {
            '__init__', '__manifest__', 'res_partner', 'res_config_settings'
        }
        
        if file_name in special_files:
            return True
        
        # Dateien in static/ und wizard/ Ordnern überspringen
        relative_path = file_path.relative_to(self.base_path)
        if any(part in {'static', 'wizard'} for part in relative_path.parts):
            return True
            
        # Security CSV-Dateien haben eigene Namenskonvention
        if file_path.parent.name == 'security' and file_path.suffix == '.csv':
            return True
            
        # Prüfe ob Modulname im Dateinamen enthalten ist (nur für Python/XML Dateien)
        if file_path.suffix.lower() in {'.py', '.xml'} and module_name not in file_name:
            self.log_warning(f"Datei '{file_path}' sollte den Modulnamen '{module_name}' enthalten")
            return False
            
        return True

    def add_header_to_file(self, file_path: Path) -> bool:
        """Fügt Header zu Datei hinzu (idempotent)"""
        try:
            # Datei lesen
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            file_extension = file_path.suffix.lower()
            
            # Prüfen ob Header bereits vorhanden (idempotent)
            if self.has_license_header(content, file_extension):
                return True  # Keine Änderung nötig
            
            # Header generieren und hinzufügen
            header = self.generate_header(file_path)
            new_content = header + content
            
            # Datei schreiben (fehlertolerant)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            creation_date = self.get_file_creation_date(file_path)
            self.log_change(f"Header hinzugefügt zu: {file_path} (Erstellt: {creation_date})")
            return True
            
        except Exception as e:
            self.log_error(f"Konnte Header nicht zu {file_path} hinzufügen: {e}")
            return False

    def check_file(self, file_path: Path, module_name: str):
        """Prüft eine einzelne Datei"""
        # Dateinamen prüfen
        self.check_file_naming(file_path, module_name)
        
        # Header prüfen/hinzufügen
        if file_path.suffix.lower() in HEADER_EXTENSIONS:
            self.add_header_to_file(file_path)

    def check_current_module(self):
        """Prüft das aktuelle Verzeichnis als Odoo-Modul"""
        self.module_name = self.get_module_name()
        if not self.module_name:
            self.log_error(f"Das aktuelle Verzeichnis '{self.base_path.name}' ist kein zw_ Modul")
            return False
            
        print(f"\n🔍 Prüfe aktuelles Modul: {self.base_path.name} (Modulname: {self.module_name})")
        
        # Manifest-Datei prüfen
        manifest_file = self.base_path / '__manifest__.py'
        if not manifest_file.exists():
            self.log_error(f"Keine __manifest__.py im aktuellen Modul-Verzeichnis")
        
        # Standard Odoo-Ordnerstruktur definieren
        standard_folders = {
            'models', 'views', 'controllers', 'data', 'security', 
            'report', 'static', 'wizard', 'tests'
        }
        
        # Durch alle Dateien und Unterordner iterieren
        for root, dirs, files in os.walk(self.base_path):
            root_path = Path(root)
            
            # Ordner filtern (fehlertolerant) - static und wizard ignorieren
            dirs[:] = [d for d in dirs if not self.should_ignore_folder(d)]
            
            # Dateien prüfen
            for file_name in files:
                file_path = root_path / file_name
                try:
                    self.check_file(file_path, self.module_name)
                except Exception as e:
                    self.log_error(f"Fehler beim Prüfen von {file_path}: {e}")
        
        return True

    def run_check(self):
        """Hauptfunktion - startet die Überprüfung des aktuellen Moduls"""
        print(f"🚀 Starte Odoo-Modul-Überprüfung in: {self.base_path}")
        print(f"📅 Aktuelles Jahr: {CURRENT_YEAR}")
        print(f"👤 Author: {AUTHOR}")
        print("=" * 60)
        
        try:
            # Prüfe nur das aktuelle Verzeichnis als Modul
            if not self.check_current_module():
                self.log_error("Das aktuelle Verzeichnis ist kein gültiges zw_ Modul")
                return
        
        except Exception as e:
            self.log_error(f"Unerwarteter Fehler: {e}")
        
        # Zusammenfassung ausgeben
        self.print_summary()

    def print_summary(self):
        """Gibt eine Zusammenfassung der Ergebnisse aus"""
        print("\n" + "=" * 60)
        print("📊 ZUSAMMENFASSUNG")
        print("=" * 60)
        
        print(f"✅ Änderungen vorgenommen: {len(self.changes_made)}")
        for change in self.changes_made:
            print(f"   • {change}")
        
        print(f"\n⚠️  Warnungen: {len(self.warnings)}")
        for warning in self.warnings:
            print(f"   • {warning}")
        
        print(f"\n❌ Fehler: {len(self.errors)}")
        for error in self.errors:
            print(f"   • {error}")
        
        if not self.errors and not self.warnings:
            print("\n🎉 Alle Module sind korrekt strukturiert!")
        elif not self.errors:
            print("\n✅ Überprüfung abgeschlossen (nur Warnungen)")
        else:
            print("\n❌ Überprüfung abgeschlossen mit Fehlern")

def main():
    """Hauptfunktion des Skripts"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Überprüft und korrigiert die Struktur des aktuellen Odoo-Moduls",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  cd zw_inventory_management && python odoo_checker.py    # Im Modul-Ordner ausführen
  python odoo_checker.py /pfad/zu/zw_mein_modul          # Spezifisches zw_ Modul
  python odoo_checker.py --dry-run                       # Nur Überprüfung, keine Änderungen

Wichtig: Das Skript muss in einem Ordner ausgeführt werden, der mit 'zw_' anfängt.
Alle Unterordner folgen dem Standard Odoo-Naming (models/, views/, controllers/, etc.)
        """
    )
    
    parser.add_argument(
        'path', 
        nargs='?', 
        default='.', 
        help='Pfad zum zw_ Odoo-Modul (Standard: aktueller Ordner)'
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Nur überprüfen, keine Änderungen vornehmen'
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY-RUN Modus: Keine Änderungen werden vorgenommen")
    
    checker = OdooModuleChecker(args.path)
    
    # Bei dry-run die add_header_to_file Methode überschreiben
    if args.dry_run:
        def dry_run_add_header(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if not checker.has_license_header(content, file_path.suffix.lower()):
                    creation_date = checker.get_file_creation_date(file_path)
                    checker.log_change(f"WÜRDE Header hinzufügen zu: {file_path} (Erstellt: {creation_date})")
            except Exception as e:
                checker.log_error(f"Fehler beim Dry-Run für {file_path}: {e}")
            return True
        checker.add_header_to_file = dry_run_add_header
    
    checker.run_check()
    
    # Exit-Code basierend auf Ergebnissen
    if checker.errors:
        sys.exit(1)
    elif checker.warnings:
        sys.exit(2)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()