#!/usr/bin/env python3
"""
Encoding Verification Tool für Odoo Module
==========================================

Detaillierte Verifikation von File-Encodings mit verschiedenen Methoden.
Zeigt den Unterschied zwischen ASCII-content und UTF-8-encoding.

Usage: python3 encoding_verification.py [module_path]
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class EncodingVerifier:
    """Umfassende Encoding-Verifikation"""
    
    def __init__(self, module_path: str = "."):
        self.module_path = Path(module_path).resolve()
        
    def log(self, message: str, color: str = Colors.WHITE):
        """Colored logging"""
        print(f"{color}{message}{Colors.END}")
    
    def get_file_encoding_methods(self, file_path: Path) -> Dict[str, str]:
        """Verschiedene Methoden zur Encoding-Erkennung"""
        results = {}
        
        try:
            # Method 1: file command (Linux/macOS)
            try:
                result = subprocess.run(['file', '-b', '--mime-encoding', str(file_path)], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    results['file_command'] = result.stdout.strip()
                else:
                    results['file_command'] = 'unknown'
            except (subprocess.SubprocessError, FileNotFoundError):
                results['file_command'] = 'not_available'
            
            # Method 2: chardet (wenn verfügbar)
            if HAS_CHARDET:
                try:
                    with open(file_path, 'rb') as f:
                        raw_data = f.read()
                    detected = chardet.detect(raw_data)
                    encoding = detected.get('encoding', 'unknown')
                    confidence = detected.get('confidence', 0.0)
                    results['chardet'] = f"{encoding} (confidence: {confidence:.2f})"
                except Exception:
                    results['chardet'] = 'error'
            else:
                results['chardet'] = 'not_installed'
            
            # Method 3: Python's encoding detection
            encodings_to_test = ['utf-8', 'ascii', 'latin-1', 'cp1252']
            successful_encodings = []
            
            for encoding in encodings_to_test:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        # Check if we can encode back to the same encoding
                        content.encode(encoding)
                        successful_encodings.append(encoding)
                except (UnicodeDecodeError, UnicodeEncodeError):
                    continue
            
            results['python_compatible'] = ', '.join(successful_encodings) if successful_encodings else 'none'
            
            # Method 4: Check for non-ASCII characters
            try:
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                
                has_non_ascii = any(byte > 127 for byte in raw_data)
                results['has_non_ascii'] = 'yes' if has_non_ascii else 'no'
                
                # Try to decode as ASCII
                try:
                    raw_data.decode('ascii')
                    results['ascii_decodable'] = 'yes'
                except UnicodeDecodeError:
                    results['ascii_decodable'] = 'no'
                    
            except Exception:
                results['has_non_ascii'] = 'error'
                results['ascii_decodable'] = 'error'
            
            # Method 5: Check XML/Python declaration
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    first_lines = f.read(500)  # First 500 chars
                
                if file_path.suffix == '.xml':
                    if 'encoding="utf-8"' in first_lines:
                        results['declared_encoding'] = 'utf-8 (XML)'
                    elif 'encoding=' in first_lines:
                        import re
                        match = re.search(r'encoding="([^"]*)"', first_lines)
                        if match:
                            results['declared_encoding'] = f'{match.group(1)} (XML)'
                        else:
                            results['declared_encoding'] = 'unknown (XML)'
                    else:
                        results['declared_encoding'] = 'none (XML)'
                        
                elif file_path.suffix == '.py':
                    if 'coding:' in first_lines or 'coding=' in first_lines:
                        import re
                        match = re.search(r'coding[:=]\s*([-\w.]+)', first_lines)
                        if match:
                            results['declared_encoding'] = f'{match.group(1)} (Python)'
                        else:
                            results['declared_encoding'] = 'found but unparsable (Python)'
                    else:
                        results['declared_encoding'] = 'none (Python)'
                else:
                    results['declared_encoding'] = 'not_applicable'
                    
            except Exception:
                results['declared_encoding'] = 'error'
                
        except Exception as e:
            results['error'] = str(e)
        
        return results
    
    def check_xml_syntax(self, file_path: Path) -> Dict[str, str]:
        """XML-Syntax Verifikation"""
        results = {}
        
        if file_path.suffix != '.xml':
            results['xml_syntax'] = 'not_xml'
            return results
        
        try:
            import xml.etree.ElementTree as ET
            ET.parse(file_path)
            results['xml_syntax'] = 'valid'
        except ET.ParseError as e:
            results['xml_syntax'] = f'invalid: {e}'
        except Exception as e:
            results['xml_syntax'] = f'error: {e}'
        
        return results
    
    def verify_encoding(self, file_path: Path) -> Dict[str, any]:
        """Komplette Encoding-Verifikation für eine Datei"""
        
        # Basic info
        info = {
            'file_path': file_path,
            'file_size': file_path.stat().st_size if file_path.exists() else 0,
            'file_type': file_path.suffix
        }
        
        # Encoding methods
        encoding_results = self.get_file_encoding_methods(file_path)
        info.update(encoding_results)
        
        # XML syntax check
        xml_results = self.check_xml_syntax(file_path)
        info.update(xml_results)
        
        # Assessment
        info['assessment'] = self.assess_encoding_status(info)
        
        return info
    
    def assess_encoding_status(self, info: Dict) -> str:
        """Bewertung des Encoding-Status"""
        
        # Check for errors
        if 'error' in info:
            return f"ERROR: {info['error']}"
        
        # XML files
        if info['file_type'] == '.xml':
            if info.get('xml_syntax', '').startswith('invalid'):
                return f"BROKEN: {info['xml_syntax']}"
            
            if info.get('declared_encoding', '').startswith('utf-8'):
                if info.get('ascii_decodable') == 'yes':
                    return "PERFECT: UTF-8 declared, ASCII content (fully compatible)"
                elif info.get('has_non_ascii') == 'no':
                    return "PERFECT: UTF-8 declared, pure ASCII content"
                else:
                    return "GOOD: UTF-8 declared with non-ASCII content"
            else:
                return f"WARNING: Non-UTF-8 declaration: {info.get('declared_encoding', 'unknown')}"
        
        # Python files
        elif info['file_type'] == '.py':
            if info.get('has_non_ascii') == 'no':
                return "PERFECT: Pure ASCII content (Python default)"
            elif info.get('declared_encoding', '').startswith('utf-8'):
                return "GOOD: UTF-8 declared for non-ASCII content"
            else:
                return "WARNING: Non-ASCII content without proper encoding declaration"
        
        # Other files
        else:
            if info.get('ascii_decodable') == 'yes':
                return "OK: ASCII compatible"
            else:
                return "INFO: Binary or non-ASCII content"
    
    def print_file_report(self, info: Dict):
        """Detaillierter Report für eine Datei"""
        
        file_path = info['file_path']
        assessment = info['assessment']
        
        # Color based on assessment
        if assessment.startswith('PERFECT'):
            color = Colors.GREEN
            status_icon = "✅"
        elif assessment.startswith('GOOD'):
            color = Colors.CYAN
            status_icon = "👍"
        elif assessment.startswith('OK'):
            color = Colors.BLUE
            status_icon = "ℹ️"
        elif assessment.startswith('WARNING'):
            color = Colors.YELLOW
            status_icon = "⚠️"
        elif assessment.startswith('BROKEN') or assessment.startswith('ERROR'):
            color = Colors.RED
            status_icon = "❌"
        else:
            color = Colors.WHITE
            status_icon = "?"
        
        self.log(f"\n{status_icon} {file_path.name}", color)
        self.log(f"   Assessment: {assessment}", color)
        
        # Technical details
        self.log(f"   File command: {info.get('file_command', 'unknown')}", Colors.WHITE)
        if HAS_CHARDET:
            self.log(f"   Chardet: {info.get('chardet', 'unknown')}", Colors.WHITE)
        self.log(f"   Python compatible: {info.get('python_compatible', 'unknown')}", Colors.WHITE)
        self.log(f"   Has non-ASCII: {info.get('has_non_ascii', 'unknown')}", Colors.WHITE)
        self.log(f"   ASCII decodable: {info.get('ascii_decodable', 'unknown')}", Colors.WHITE)
        
        if info.get('declared_encoding') != 'not_applicable':
            self.log(f"   Declared encoding: {info.get('declared_encoding', 'none')}", Colors.WHITE)
        
        if info['file_type'] == '.xml':
            self.log(f"   XML syntax: {info.get('xml_syntax', 'unknown')}", Colors.WHITE)
    
    def run_verification(self):
        """Hauptverifikation"""
        
        self.log("🔍 COMPREHENSIVE ENCODING VERIFICATION", Colors.BOLD + Colors.CYAN)
        self.log("=" * 60, Colors.BOLD)
        
        # Check if module exists
        if not self.module_path.exists():
            self.log(f"❌ Path does not exist: {self.module_path}", Colors.RED)
            return False
        
        # Find relevant files
        xml_files = list(self.module_path.glob('**/*.xml'))
        py_files = list(self.module_path.glob('**/*.py'))
        
        all_files = xml_files + py_files
        
        if not all_files:
            self.log("No XML or Python files found", Colors.YELLOW)
            return True
        
        self.log(f"📁 Module: {self.module_path.name}", Colors.BOLD)
        self.log(f"📄 Found {len(xml_files)} XML files, {len(py_files)} Python files", Colors.WHITE)
        
        if not HAS_CHARDET:
            self.log("⚠️ chardet not available - using fallback detection", Colors.YELLOW)
        
        # Verify each file
        perfect_count = 0
        good_count = 0
        warning_count = 0
        error_count = 0
        
        for file_path in sorted(all_files):
            try:
                info = self.verify_encoding(file_path)
                self.print_file_report(info)
                
                # Count by status
                assessment = info['assessment']
                if assessment.startswith('PERFECT'):
                    perfect_count += 1
                elif assessment.startswith('GOOD'):
                    good_count += 1
                elif assessment.startswith('WARNING'):
                    warning_count += 1
                elif assessment.startswith('BROKEN') or assessment.startswith('ERROR'):
                    error_count += 1
                    
            except Exception as e:
                self.log(f"❌ {file_path.name}: Verification error - {e}", Colors.RED)
                error_count += 1
        
        # Summary
        self.log("\n" + "=" * 60, Colors.BOLD)
        self.log("📊 VERIFICATION SUMMARY", Colors.BOLD)
        self.log("=" * 60, Colors.BOLD)
        
        total_files = len(all_files)
        self.log(f"📄 Total files checked: {total_files}", Colors.WHITE)
        self.log(f"✅ Perfect: {perfect_count}", Colors.GREEN)
        self.log(f"👍 Good: {good_count}", Colors.CYAN)
        self.log(f"⚠️ Warnings: {warning_count}", Colors.YELLOW)
        self.log(f"❌ Errors: {error_count}", Colors.RED)
        
        # Interpretation
        self.log(f"\n💡 INTERPRETATION:", Colors.BOLD + Colors.CYAN)
        
        if error_count > 0:
            self.log(f"❌ {error_count} files have errors - fix required!", Colors.RED)
            success = False
        elif warning_count > 0:
            self.log(f"⚠️ {warning_count} files have warnings - review recommended", Colors.YELLOW)
            success = True
        else:
            self.log("🎉 All files have correct encoding!", Colors.GREEN)
            success = True
        
        # ASCII explanation
        if perfect_count > 0:
            self.log(f"\nℹ️ Why 'file' command shows ASCII:", Colors.CYAN)
            self.log("   - ASCII is a subset of UTF-8", Colors.WHITE)
            self.log("   - If file contains only ASCII chars, 'file' shows ASCII", Colors.WHITE)
            self.log("   - This is NORMAL and CORRECT for XML with UTF-8 declaration", Colors.WHITE)
            self.log("   - Odoo will treat these files as UTF-8 because of XML declaration", Colors.WHITE)
        
        return success

def main():
    """CLI Interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify encoding in Odoo modules")
    parser.add_argument('module_path', nargs='?', default='.', 
                       help='Path to module (default: current directory)')
    
    args = parser.parse_args()
    
    verifier = EncodingVerifier(args.module_path)
    success = verifier.run_verification()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
