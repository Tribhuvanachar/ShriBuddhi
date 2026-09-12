#!/usr/bin/env python3
"""Downloads VedaVaNi's recitation audio from its Cloudflare R2 buckets and
slices it into per-unit clips, pairing each clip with the matching mūla text
already bundled in vedavani-assets.zip (extracted at the repo root as
VEDAVANI_ASSETS_DIR below).

URL schemes were reconstructed by decompiling VedaVaNi_1.3.3.apk's classes.dex
directly (not guessed, not taken on faith from a third-party report) --
see dge/PROJECT_STATUS.md for the walkthrough. Two independently different
schemes, one per Veda:

  Rigveda   (classes w3.d, Q3.f0):
      <base>/<mandala, zero-padded to 3 digits>/<sukta, zero-padded to 3 digits>/sukta.mp3
      One whole-Sukta MP3 per (mandala, sukta, patha) -- NOT per-rik. VedaVaNi's
      own Room schema has a word_timestamps table, but nothing in the decompiled
      playback path actually reads or writes it; no per-rik split point was found
      anywhere (bundled assets or code), so Rigveda output here is honestly
      per-SUKTA, not per-rik, until real timestamp data turns up.

  Yajurveda (classes w3.n/w3.o/w3.p, ui.screens.yajurveda.X/Q):
      <base>/<rootFolder>/<subfolder>/<filePrefix> <part, 0-padded if the
      section says so>.mp3   -- one MP3 per (kanda-or-ashtaka, part/prashna)
      for Samhita/Brahmanam, sliced into real per-mantra clips using the
      startMs/endMs boundaries in the bundled boundaries/*.json (this data
      genuinely exists locally, unlike Rigveda's word_timestamps).
      Aranyaka is 8 named single-file tracks, no part/prashna splitting.

Nothing here has been run against the real network -- this repo's dev sandbox
blocks pub-*.r2.dev outbound (see PROJECT_STATUS.md). This script is meant to
run inside the GitHub Action (tools/../.github/workflows/vedavani-extract.yml),
which has ordinary internet access. Run with --dry-run first to sanity check
the URL list and slice plan without downloading anything.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
VEDAVANI_ASSETS_DIR = os.environ.get(
    'VEDAVANI_ASSETS_DIR',
    os.path.join(REPO_ROOT, 'vedavani-assets-extracted', 'assets')
)

RIGVEDA_BASES = {
    'kanchi': 'https://pub-52c26d6f46f4437597b75ce81269a56c.r2.dev',
    'sringeri': 'https://pub-6a4f361621524b91b3b9ba5bfc768dd1.r2.dev',
}
YAJURVEDA_BASE = 'https://pub-6da4d216b53a4695b3f92540026267f5.r2.dev'

# Reconstructed verbatim from w3.n's <clinit> (see module docstring) --
# (number, englishName, devanagariName, partCount, rootFolder, subfolder, filePrefix, zeroPadded)
YAJURVEDA_SAMHITA_KANDAS = [
    (1, 'Kanda 1 – Prathama', 8, '01 Krishna Yajurveda Samhita_AUDIO_MP3 COMPLETE SR', 'KYS 01 Prathama', 'KYS Prathama', False),
    (2, 'Kanda 2 – Dweetiya', 6, '01 Krishna Yajurveda Samhita_AUDIO_MP3 COMPLETE SR', 'KYS 02 Dweetiya', 'KYS Dweetiya', False),
    (3, 'Kanda 3 – Thrithiya', 5, '01 Krishna Yajurveda Samhita_AUDIO_MP3 COMPLETE SR', 'KYS 03 Thritiya', 'KYS Thrithiya', False),
    (4, 'Kanda 4 – Chathurtha', 7, '01 Krishna Yajurveda Samhita_AUDIO_MP3 COMPLETE SR', 'KYS 04 Chathurtha', 'KYS Chathurtha', False),
    (5, 'Kanda 5 – Panchama', 7, '01 Krishna Yajurveda Samhita_AUDIO_MP3 COMPLETE SR', 'KYS 05 Panchama', 'KYS Panchama', False),
    (6, 'Kanda 6 – Shastha', 6, '01 Krishna Yajurveda Samhita_AUDIO_MP3 COMPLETE SR', 'KYS 06 Shastha', 'KYS Shastha', False),
    (7, 'Kanda 7 – Sapthama', 5, '01 Krishna Yajurveda Samhita_AUDIO_MP3 COMPLETE SR', 'KYS 07 Sapthama', 'KYS Sapthama', False),
]
YAJURVEDA_BRAHMANAM_ASHTAKAS = [
    (1, 'Ashtaka 1 – Prathama', 8, '02 Krishna Yajurveda Brahmanam_AUDIO_MP3 COMPLETE SR', 'KYB 01 Prathama', 'KYB Prathama', False),
    (2, 'Ashtaka 2 – Dweetiya', 8, '02 Krishna Yajurveda Brahmanam_AUDIO_MP3 COMPLETE SR', 'KYB 02 Dweetiya', 'KYB Dweetiya', False),
    (3, 'Ashtaka 3 – Thrithiya', 12, '02 Krishna Yajurveda Brahmanam_AUDIO_MP3 COMPLETE SR', 'KYB 03 Thrithiya', 'KYB Thrithiya', True),
]
YAJURVEDA_ARANYAKA_TRACKS = [
    'ArunaPrashnah', 'Mahanarayanopanishat', 'Chittissruk', 'DevaVai',
    'NamoVache', 'PareyuvaMsam', 'SahaVai', 'Taittiriyopanishat',
]
YAJURVEDA_ARANYAKA_FOLDER = '03 Krishna Yajurveda Aaranyakam_AUDIO_MP3 COMPLETE SR'


def log(msg):
    print(msg, flush=True)


def http_get(url, dest_path, dry_run, retries=3):
    if dry_run:
        log(f'[dry-run] would GET {url} -> {dest_path}')
        return True
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        log(f'  skip (already downloaded): {dest_path}')
        return True
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'bhumandala-dge-vedavani-extract/1.0'})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            with open(dest_path, 'wb') as f:
                f.write(data)
            log(f'  ok ({len(data)} bytes): {url}')
            return True
        except urllib.error.HTTPError as e:
            log(f'  HTTP {e.code} on attempt {attempt}/{retries}: {url}')
            if e.code == 404:
                return False  # genuinely missing, don't burn retries
        except Exception as e:
            log(f'  error on attempt {attempt}/{retries}: {url} -- {e}')
        time.sleep(2 * attempt)
    return False


def ffmpeg_slice(src_mp3, start_ms, end_ms, dest_mp3, dry_run):
    if dry_run:
        log(f'[dry-run] would slice {src_mp3} [{start_ms}-{end_ms}ms] -> {dest_mp3}')
        return True
    os.makedirs(os.path.dirname(dest_mp3), exist_ok=True)
    duration_s = (end_ms - start_ms) / 1000.0
    start_s = start_ms / 1000.0
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-ss', f'{start_s:.3f}', '-i', src_mp3, '-t', f'{duration_s:.3f}',
        '-c', 'copy', dest_mp3,
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f'  ffmpeg failed for {dest_mp3}: {e}')
        return False


def load_json(rel_path):
    path = os.path.join(VEDAVANI_ASSETS_DIR, rel_path)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------- Rigveda ---

def rigveda_sukta_counts():
    """{mandala_number: sukta_count}, from rigveda_krama_mapping.json's own
    "Mandala N - Sukta M" keys -- the authoritative sukta list (1028 total,
    matching the classical count: 191/43/62/58/87/75/104/103/114/191).
    NOT derived from rig_veda_multiscript.json: that file's "sukta" array
    name is misleading -- each entry in it is actually one RIK (verse),
    numbered per-adhyaya, not one sukta. Counting those directly gives a
    wildly wrong per-mandala total (confirmed while building this script)."""
    mapping = load_json('rigveda_krama_mapping.json')
    counts = {}
    for key in mapping:
        mandala_str = key.split(' - Sukta ')[0].replace('Mandala ', '')
        counts[int(mandala_str)] = counts.get(int(mandala_str), 0) + 1
    return counts


def run_rigveda(out_dir, pathas, mandalas, dry_run):
    counts = rigveda_sukta_counts()

    for mandala in mandalas:
        if mandala not in counts:
            log(f'Mandala {mandala}: not found in rigveda_krama_mapping.json, skipping.')
            continue
        n_suktas = counts[mandala]
        for sukta_num in range(1, n_suktas + 1):
            for patha in pathas:
                base = RIGVEDA_BASES[patha]
                url = f'{base}/{mandala:03d}/{sukta_num:03d}/sukta.mp3'
                dest = os.path.join(out_dir, 'rigveda', patha, f'mandala_{mandala:02d}', f'sukta_{sukta_num:03d}.mp3')
                ok = http_get(url, dest, dry_run)
                if not ok:
                    log(f'  MISSING (real 404 or repeated failure): mandala {mandala} sukta {sukta_num} ({patha})')

    # Text side deliberately NOT written per-sukta here: rig_veda_multiscript.json
    # only gives riks grouped by adhyaya (an adhyaya can span, or fall inside,
    # multiple suktas), with no sukta boundary markers of its own. Matching
    # rik ranges to individual suktas needs the Anukramani verse-count field
    # (Anukramani/Mandala_N.txt, "hymn.verses.seer.divinity.meter") as a
    # cross-reference and hasn't been verified yet -- shipping a guessed
    # rik<->sukta split here would risk mismatched text/audio pairs, which
    # is worse than shipping audio-only for now. Flagged as a follow-up
    # rather than silently done wrong.
    for mandala in mandalas:
        log(f'Mandala {mandala}: text pairing skipped (needs Anukramani verse-count cross-reference first — see comment above).')


# -------------------------------------------------------------- Yajurveda ---

def yajurveda_part_url(section, part):
    number, name, part_count, root_folder, subfolder, file_prefix, zero_padded = section
    idx = f'{part:02d}' if zero_padded else str(part)
    filename = f'{file_prefix} {idx}.mp3'
    quote = urllib.parse.quote
    return f'{YAJURVEDA_BASE}/{quote(root_folder)}/{quote(subfolder)}/{quote(filename)}'


def run_yajurveda_section(kind, sections, boundary_prefix, text_key, out_dir, dry_run, only_numbers=None):
    text_doc = load_json(f'yajurveda/{text_key}.json')
    # text_doc: {..., 'kandas' or 'ashtakas': [{kanda/ashtaka: N, prashnas: [{prashna: N, anuvakas:[{anuvaka:N, mantras:[{mantra:N, text}]}]}]}]}
    outer_key = 'kandas' if text_key == 'samhita' else 'ashtakas'
    outer_id_key = 'kanda' if text_key == 'samhita' else 'ashtaka'
    text_by_outer = {o[outer_id_key]: o for o in text_doc[outer_key]}

    for section in sections:
        number = section[0]
        if only_numbers and number not in only_numbers:
            continue
        _, name, part_count, *_rest = section
        outer_text = text_by_outer.get(number)
        for part in range(1, part_count + 1):
            url = yajurveda_part_url(section, part)
            raw_dest = os.path.join(out_dir, 'yajurveda', kind, f'{text_key}_{number}_{part}_raw.mp3')
            ok = http_get(url, raw_dest, dry_run)
            if not ok:
                log(f'  MISSING: {kind} {number}/{part} ({name})')
                continue

            boundary_path = f'yajurveda/boundaries/{boundary_prefix}_{number}_{part}.json'
            try:
                boundary = load_json(boundary_path)
            except FileNotFoundError:
                log(f'  no boundary file for {boundary_path} -- keeping the whole-part MP3 unsliced.')
                continue

            prashna_text = None
            if outer_text:
                for p in outer_text.get('prashnas', []):
                    if p.get('prashna') == part:
                        prashna_text = p
                        break

            for m in boundary.get('mantras', []):
                anuvaka_no, mantra_no = m['anuvakaNumber'], m['mantraNumber']
                clip_dest = os.path.join(
                    out_dir, 'yajurveda', kind, f'{text_key}_{number}', f'prashna_{part}',
                    f'anuvaka_{anuvaka_no}_mantra_{mantra_no}.mp3'
                )
                if not dry_run and not os.path.exists(raw_dest):
                    continue
                ffmpeg_slice(raw_dest, m['startMs'], m['endMs'], clip_dest, dry_run)

            if prashna_text:
                text_out = os.path.join(out_dir, 'yajurveda', 'text', f'{text_key}_{number}_prashna_{part}.json')
                if not dry_run:
                    os.makedirs(os.path.dirname(text_out), exist_ok=True)
                    with open(text_out, 'w', encoding='utf-8') as f:
                        json.dump(prashna_text, f, ensure_ascii=False, indent=1)


def run_yajurveda_aranyaka(out_dir, dry_run, only_names=None):
    text_doc = load_json('yajurveda/aranyaka.json')
    for track_name in YAJURVEDA_ARANYAKA_TRACKS:
        if only_names and track_name not in only_names:
            continue
        quote = urllib.parse.quote
        url = f'{YAJURVEDA_BASE}/{quote(YAJURVEDA_ARANYAKA_FOLDER)}/{quote(track_name)}.mp3'
        dest = os.path.join(out_dir, 'yajurveda', 'aranyaka', f'{track_name}.mp3')
        http_get(url, dest, dry_run)

        boundary_path = f'yajurveda/boundaries/aranyaka_{track_name}.json'
        try:
            boundary = load_json(boundary_path)
        except FileNotFoundError:
            boundary = None
        if boundary:
            for section in boundary.get('sections', boundary.get('mantras', [])):
                pass  # aranyaka boundary shape not yet confirmed against a real section list -- slicing left for a follow-up once verified against actual downloaded audio length
        text_out = os.path.join(out_dir, 'yajurveda', 'text', f'aranyaka_{track_name}.json')
        if not dry_run:
            os.makedirs(os.path.dirname(text_out), exist_ok=True)
            with open(text_out, 'w', encoding='utf-8') as f:
                json.dump(text_doc, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--veda', choices=['rigveda', 'yajurveda', 'both'], default='both')
    ap.add_argument('--patha', choices=['kanchi', 'sringeri', 'both'], default='both',
                     help='Rigveda only -- which reciter\'s audio to fetch.')
    ap.add_argument('--mandalas', default='1-10', help='Rigveda only, e.g. "1" or "1-3" or "1,5,9".')
    ap.add_argument('--yajurveda-part', choices=['samhita', 'brahmanam', 'aranyaka', 'all'], default='all')
    ap.add_argument('--out-dir', default=os.path.join(REPO_ROOT, 'vedavani_audio_out'))
    ap.add_argument('--dry-run', action='store_true', help='Print what would happen, download/slice nothing.')
    args = ap.parse_args()

    def parse_range(s, lo, hi):
        out = set()
        for part in s.split(','):
            part = part.strip()
            if '-' in part:
                a, b = part.split('-')
                out.update(range(int(a), int(b) + 1))
            elif part:
                out.add(int(part))
        return sorted(n for n in out if lo <= n <= hi)

    pathas = ['kanchi', 'sringeri'] if args.patha == 'both' else [args.patha]
    mandalas = parse_range(args.mandalas, 1, 10)

    if not os.path.isdir(VEDAVANI_ASSETS_DIR):
        log(f'ERROR: {VEDAVANI_ASSETS_DIR} not found -- extract vedavani-assets.zip there first '
            f'(the workflow does this before calling this script).')
        sys.exit(1)

    if args.veda in ('rigveda', 'both'):
        log(f'=== Rigveda: mandalas {mandalas}, patha(s) {pathas} ===')
        run_rigveda(args.out_dir, pathas, mandalas, args.dry_run)

    if args.veda in ('yajurveda', 'both'):
        if args.yajurveda_part in ('samhita', 'all'):
            log('=== Yajurveda Samhita ===')
            run_yajurveda_section('samhita', YAJURVEDA_SAMHITA_KANDAS, 'samhita', 'samhita', args.out_dir, args.dry_run)
        if args.yajurveda_part in ('brahmanam', 'all'):
            log('=== Yajurveda Brahmanam ===')
            run_yajurveda_section('brahmanam', YAJURVEDA_BRAHMANAM_ASHTAKAS, 'brahmanam', 'brahmanam', args.out_dir, args.dry_run)
        if args.yajurveda_part in ('aranyaka', 'all'):
            log('=== Yajurveda Aranyaka ===')
            run_yajurveda_aranyaka(args.out_dir, args.dry_run)

    log('Done.')


if __name__ == '__main__':
    main()
