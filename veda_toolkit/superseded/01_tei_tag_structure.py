from lxml import etree
from collections import Counter

tei_path = "vedaweb_work/extracted/cceh-c-salt_vedaweb_tei-f975755/vedaweb_corpus.tei"
parser = etree.XMLParser(recover=True, huge_tree=True)
tree = etree.parse(tei_path, parser)
root = tree.getroot()

def local_tag(e):
    return etree.QName(e).localname

# 1. Every distinct tag name in the whole document, with counts.
print("=" * 60)
print("ALL TAG NAMES (with counts):")
print("=" * 60)
tag_counts = Counter(local_tag(e) for e in root.iter())
for tag, count in tag_counts.most_common():
    print(f"  {tag}: {count}")

# 2. Every distinct 'type' attribute value seen on any element.
print("\n" + "=" * 60)
print("ALL @type ATTRIBUTE VALUES SEEN (with the tag they're on):")
print("=" * 60)
type_vals = Counter((local_tag(e), e.get("type")) for e in root.iter() if e.get("type"))
for (tag, typ), count in type_vals.most_common(40):
    print(f"  <{tag} type=\"{typ}\">: {count}")

# 3. Raw structure near the top of <text>/<body> — first few levels only.
print("\n" + "=" * 60)
print("STRUCTURE SAMPLE (first 4 levels under <text>):")
print("=" * 60)
text_elem = next((e for e in root.iter() if local_tag(e) == "text"), root)

def show(elem, depth=0, max_depth=4):
    if depth > max_depth:
        return
    attrs = " ".join(f'{k}="{v}"' for k, v in elem.attrib.items())
    print("  " * depth + f"<{local_tag(elem)}{' ' + attrs if attrs else ''}>")
    for child in list(elem)[:3]:  # only first 3 children at each level, to keep this short
        show(child, depth + 1, max_depth)

show(text_elem)

# 4. Raw XML snippet — first stanza-ish chunk of actual markup, verbatim.
print("\n" + "=" * 60)
print("RAW XML SNIPPET (first 3000 characters under <text>):")
print("=" * 60)
raw = etree.tostring(text_elem, pretty_print=True, encoding="unicode")
print(raw[:3000])
