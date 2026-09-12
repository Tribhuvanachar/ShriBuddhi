#!/usr/bin/env python3
# Unified Dhātuvṛtti extractor from samsaadhanii/scl (GPL-2.0):
# Mādhavīya + Kṣīrataraṅgiṇī + Dhātupradīpa. Produces one per-dhātu file
#   data/vyakarana/vritti/<code>.json = {code, dhatu, vrittis:[{source,name,author,no,meaning,text}], sources[]}
# matched to the DGE Dhātupāṭha by (gaṇa, normalized form), unambiguous only.
import re, json, os, glob
SCL="/tmp/scl/dhaatupaatha/files"
DHATU="/tmp/bhumandala/dge/data/vedanga/vyakarana/dhatupatha/data.json"
OUTDIR="/tmp/bhumandala/dge/data/vedanga/vyakarana/vritti"

VRITTIS=[
 ("madhaviya","माधवीयधातुवृत्तिः","सायणः","madhaviya_XAwuvqwwi_new.xml"),
 ("kshira","क्षीरतरङ्गिणी","क्षीरस्वामी","kRIrawarangiNI_new.xml"),
 ("dhatupradipa","धातुप्रदीपः","मैत्रेयरक्षितः","XAwupraxIpaH_new.xml"),
]
def norm(dev): return re.sub(r'[्ृॄॢॣंःँ\s]','',dev or '')
GNAME={'भ्वादिगणः':1,'अदादिगणः':2,'जुहोत्यादिगणः':3,'दिवादिगणः':4,'स्वादिगणः':5,
       'तुदादिगणः':6,'रुधादिगणः':7,'तनादिगणः':8,'क्र्यादिगणः':9,'चुरादिगणः':10}

def parse(path):
    t=open(path,encoding='utf-8',errors='replace').read()
    toks=re.split(r'(<gaNa_name>.*?</gaNa_name>|<entry\b.*?</entry>)', t, flags=re.S)
    cur=None; m={}; dup=set()
    for tok in toks:
        g=re.match(r'<gaNa_name>(.*?)</gaNa_name>',tok,re.S)
        if g: cur=GNAME.get(re.sub(r'\s+','',g.group(1))); continue
        if not re.match(r'<entry\b.*?</entry>',tok,re.S): continue
        dm=re.search(r'<XAwu_with_iw[^>]*mAnaka_rUpa="([^"]*)"[^>]*>(.*?)</XAwu_with_iw>',tok,re.S)
        if not dm or cur is None: continue
        manaka=dm.group(1).strip()
        no=re.search(r'<entry id="(\d+)"',tok); no=no.group(1) if no else ''
        mn=re.search(r'<meaning[^>]*>(.*?)</meaning>',tok,re.S)
        meaning=re.sub(r'<[^>]+>','',mn.group(1)).strip() if mn else ''
        body=re.sub(r'<XAwu_with_iw[^>]*>.*?</XAwu_with_iw>','',tok,flags=re.S)
        body=re.sub(r'<[^>]+>',' ',body); body=re.sub(r'[ \t]+',' ',body).strip()
        k=(cur,norm(manaka))
        if k in m: dup.add(k); continue
        m[k]={"no":no,"meaning":meaning,"text":body}
    return m,dup

maps={}
for key,name,author,fn in VRITTIS:
    mp,dup=parse(os.path.join(SCL,fn)); maps[key]=(mp,dup)
    print("parsed",key,len(mp),"entries (",len(dup),"ambiguous )")

d=json.load(open(DHATU,encoding='utf-8'))
vk={}
for it in d["items"]: vk.setdefault((it["gana"],norm(it["dhatu"])),[]).append(it["id"])

os.makedirs(OUTDIR,exist_ok=True)
for old in glob.glob(os.path.join(OUTDIR,"*.json")): os.remove(old)
avail=[]; per=dict((k,0) for k,_,_,_ in VRITTIS)
for it in d["items"]:
    k=(it["gana"],norm(it["dhatu"]))
    if len(vk[k])!=1: continue
    vlist=[]
    for key,name,author,fn in VRITTIS:
        mp,dup=maps[key]
        if k in dup: continue
        e=mp.get(k)
        if not e: continue
        vlist.append({"source":key,"name":name,"author":author,"no":e["no"],"meaning":e["meaning"],"text":e["text"]})
        per[key]+=1
    if not vlist: continue
    rec={"schema":"dhatu_vrittis","code":it["id"],"dhatu":it["dhatu"],
         "sources":[v["source"] for v in vlist],"vrittis":vlist,
         "licence":"GPL-2.0 (samsaadhanii/scl) — keep attribution"}
    json.dump(rec,open(os.path.join(OUTDIR,it["id"]+".json"),"w",encoding="utf-8"),ensure_ascii=False)
    avail.append(it["id"])

idx={"schema":"vritti_index","source":"samsaadhanii/scl (GPL-2.0)","licence":"GPL-2.0 — keep attribution",
     "vrittis":[{"source":k,"name":n,"author":a} for k,n,a,_ in VRITTIS],
     "count":len(avail),"per_vritti":per,"available":avail}
json.dump(idx,open(os.path.join(OUTDIR,"index.json"),"w",encoding="utf-8"),ensure_ascii=False)
print("dhatus with >=1 vritti:",len(avail),"| per-vritti coverage:",per)
