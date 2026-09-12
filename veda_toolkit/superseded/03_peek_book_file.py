from pathlib import Path

book1 = Path("vedaweb_work/extracted/cceh-c-salt_vedaweb_tei-f975755/rv_book_01.tei")

# These files are large (10-43MB) -- read just enough to reach real body
# content without loading the whole thing.
with book1.open('r', encoding='utf-8', errors='replace') as f:
    chunk = f.read(300000)  # 300KB, comfortably past any header block

body_start = chunk.find('<body')
if body_start == -1:
    print("Didn't find <body> within the first 300,000 characters of this file --")
    print("printing from the very start instead so we can see what's there.")
    body_start = 0
else:
    print(f"Found <body at character {body_start}.")

print("=" * 60)
print("RAW XML starting at <body> (first 6000 characters):")
print("=" * 60)
print(chunk[body_start:body_start + 6000])
