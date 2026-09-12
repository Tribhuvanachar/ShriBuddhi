from pathlib import Path

extract_dir = Path("vedaweb_work/extracted")

print("=" * 60)
print("ALL FILES IN THE EXTRACTED ARCHIVE:")
print("=" * 60)
all_files = sorted(extract_dir.rglob("*"))
for f in all_files:
    if f.is_file():
        size = f.stat().st_size
        print(f"  {f.relative_to(extract_dir)}  ({size:,} bytes)")

print(f"\nTotal files: {sum(1 for f in all_files if f.is_file())}")

# Also peek inside vedaweb_corpus.tei's raw text for any <include> or
# <xi:include> references pointing at other files, since its <body> is
# empty but it declared the XInclude namespace.
print("\n" + "=" * 60)
print("SEARCHING vedaweb_corpus.tei FOR include/xi:include REFERENCES:")
print("=" * 60)
corpus_file = next(extract_dir.rglob("vedaweb_corpus.tei"))
raw_text = corpus_file.read_text(encoding="utf-8", errors="replace")
import re
includes = re.findall(r'<xi:include[^>]*/?>', raw_text)
includes += re.findall(r'<include[^>]*/?>', raw_text)
if includes:
    for inc in includes:
        print(" ", inc)
else:
    print("  No include/xi:include tags found in this file.")
