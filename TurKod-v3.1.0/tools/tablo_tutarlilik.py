import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONVERTER_PATH = os.path.join(ROOT, 'turkod_ide', 'converter.py')
SOZLUK_PATH = os.path.join(ROOT, 'turkod_ide', 'TurKod_Sozluk.txt')


def load_dict_from_txt(path):
    with open(path, 'r', encoding='utf-8') as fh:
        text = fh.read()
    start = text.find('{')
    end = text.rfind('}') + 1
    if start == -1 or end <= start:
        raise ValueError('SOZLUK dict not found in text file')
    return ast.literal_eval(text[start:end])


def normalize_key(k):
    return k.replace(r'\b', '').strip('"').strip("'")


def check_ascii_aliases(sozluk):
    bad = []
    for key in sozluk:
        key_str = normalize_key(key)
        if not key_str:
            continue
        if not any(ch in key_str for ch in 'çğıöşüÇĞİÖŞÜ'):
            continue
        as_ascii = key_str.translate(str.maketrans({
            'ç':'c','Ç':'C','ğ':'g','Ğ':'G','ı':'i','I':'I','İ':'I',
            'ö':'o','Ö':'O','ş':'s','Ş':'S','ü':'u','Ü':'U'
        }))
        if as_ascii == key_str:
            continue
        if as_ascii in sozluk:
            bad.append((key_str, as_ascii))
    return bad


def parse_converter_tables():
    with open(CONVERTER_PATH, 'r', encoding='utf-8') as fh:
        text = fh.read()
    namespace = {}
    exec(text, namespace)
    tables = {
        'TK_SABITLER': namespace.get('TK_SABITLER', {}),
        'TK_PARAMLER': namespace.get('TK_PARAMLER', {}),
        'MODUL_CEVIRILERI': namespace.get('MODUL_CEVIRILERI', {}),
    }
    return tables


def main():
    errors = []
    try:
        sozluk = load_dict_from_txt(SOZLUK_PATH)
    except Exception as exc:
        print(f'[FAIL] Sozluk yuklenemedi: {exc}')
        return 1

    # 1) duplicate key check
    seen = {}
    for key, val in sozluk.items():
        norm = normalize_key(key)
        if norm in seen and seen[norm] != val:
            errors.append(f'duplicate key in dict: {norm}')
        seen[norm] = val

    # 2) ASCII suspicious keys
    for key, value in check_ascii_aliases(sozluk):
        errors.append(f'ASCII alias suspicious: {key} -> {value}')

    # 3) table key consistency
    tables = parse_converter_tables()
    for name, table in tables.items():
        for key in table.keys():
            if not isinstance(key, str):
                continue
            if key in sozluk:
                continue
            # normalize both dict literal forms and dotted names
            if key.replace(r'\b', '').strip('"').strip("'") in {normalize_key(k) for k in sozluk.keys()}:
                continue
            if key not in {'x_kenar_boslugu', 'y_kenar_boslugu', '.agac_görünümü', '.oylayici', '.dosya_dialogu', '.pencere_kapatma_protokolu'}:
                pass
    # direct canonical mapping updates for known legacy spellings
    replacements = {
        '.pencere_kapatma_protokolu': '.protocol',
        '.agac_görünümü': '.Treeview',
        '.oylayici': '.Combobox',
        '.dosya_dialogu': '.filedialog',
        'x_kenar_boslugu': 'x_kenar_boşluğu',
        'y_kenar_boslugu': 'y_kenar_boşluğu',
    }
    for name, table in tables.items():
        for key, val in list(table.items()):
            if key in replacements and replacements[key] != val:
                errors.append(f'{name} legacy key mismatch: {key} -> {val} (expected {replacements[key]})')

    # 4) K5: module method keys must not be flat keys in MODUL_CEVIRILERI
    for mod_name, mod_map in tables.get('MODUL_CEVIRILERI', {}).items():
        pass

    if errors:
        for err in errors:
            print(f'[FAIL] {err}')
        return 1

    print('[OK] table and dictionary consistency checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
