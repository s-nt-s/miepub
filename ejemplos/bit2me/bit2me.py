#!/usr/bin/python3

import requests
import bs4
import re
from limpiar import Limpiar, vacio, heads
from bunch import Bunch

sp = re.compile(r"\s+")

ban_imgs = [i.strip() for i in open("imgs.txt").readlines() if len(i.strip())>0 ]

idc=0
ids={}

def get(url):
    r = requests.get(url)
    return bs4.BeautifulSoup(r.content, "lxml")

def append(body, li, tag):
    global idc
    global ids
    
    a = li.find("a")
    h = out.new_tag(tag)
    h.string = a.get_text()

    idc += 1
    _id = "mrk" + str(idc)
    h.attrs["id"] = _id
    body.append(h)
    url = a.attrs["href"]
    ids[url] = _id
    
    if url != "#":
        soup = get(url)
        div = soup.find("div", attrs={"class": "entry-content"})
        div.attrs.clear()
        div.name="article"
        hs=[]
        for i in range(1,7):
            h = div.findAll("h"+str(i))
            if len(h):
                hs.append(h)
        i = 3
        for _h in hs:
            for h in _h:
                h.name = "h"+str(i)
            i = i + 1
        body.append(div)

def sibling(n):
    a = n.previous_sibling
    b = n.next_sibling
    while a and not isinstance(a, bs4.Tag):
        a = a.previous_sibling
    while b and not isinstance(b, bs4.Tag):
        b = b.next_sibling
    return (a, b)

soup = get("http://blog.bit2me.com/es/guia-bitcoin/")


out = bs4.BeautifulSoup('''
<!DOCTYPE html>
<html lang="es">
    <head>
        <title>Guia BitCoin</title>
        <meta charset="utf-8"/>
        <meta content="bit2me" name="DC.creator" />
        <meta content="--epub-chapter-level 2" name="pandoc" />
        <link rel="stylesheet" type="text/css" href="theme.css">
        <link rel="stylesheet" type="text/css" href="print.css" media="print">
        <!--meta property="og:image" content="http://blog.bit2me.com/es/wp-content/uploads/sites/2/2015/11/bitcoin_terminology-2.jpg" /-->
        <meta property="og:image" content="https://i.ebayimg.com/00/s/ODAwWDYwMA==/z/xPMAAOSwO9JaGcU4/$_59.JPG" />
    </head>
    <body>
    </body>
</html>
''' , 'lxml')
body = out.body

libro=[]

lis = soup.select("aside ul.menu > li")[1:]
for li in lis:
    append(body, li, "h1")
    for l in li.findAll("li"):
        append(body, l, "h2")

lmp = Limpiar(out, Bunch(noscript=True, iframe_to_anchor=True, resolve_images=True, clear_attr=heads + ["p", "figure", "ul", "ol", "img", "a"]))
lmp.limpiar()
out = lmp.soup

for c in ".rt-reading-time, .share-before, .tm-click-to-tweet, .tm-tweet-clear".split(", "):
    for s in out.select(c):
        s.extract()

scap = re.compile(r"^\s*Siguiente\s+cap.+tulo:\s", re.MULTILINE | re.DOTALL)
for p in out.findAll("p"):
    s = p.get_text().strip()
    if scap.search(s):
        p.extract()

for i in out.findAll("img", attrs={"src": "http://blog.bit2me.com/es/wp-content/plugins/lazy-load/images/1x1.trans.gif"}):
    i.extract()

for p in out.findAll("p"):
    txt = sp.sub(" ", p.get_text().strip())
    if re.match(r"^(Este art.+culo pertenece a un bloque llamado .*4\. Transacciones\.|Imagen destacada en portada \| Bitcoinmagazine)$", txt):
        p.extract()

for hr in out.findAll("hr"):
    a, b = sibling(hr)
    if a is None or b is None or a.name.startswith("h") or b.name.startswith("h"):
        hr.extract()

for a in out.findAll("a"):
    url = a.attrs["href"]
    if url in ids:
        a.attrs["href"] = "#" + ids[url]

for i in out.findAll("img"):
    if i.attrs["src"] in ban_imgs:
        p = i.parent
        t = sp.sub("",p.get_text()).strip()
        if p.name == "figure" or (p.name=="p" and len(t)==0):
            p.extract()
        else:
            i.extract()

for i in out.findAll("span"):
    if "style" not in i.attrs:
        i.unwrap()

lmp.load(out)
lmp.limpiar()
out = lmp.soup

html = lmp.html
html = re.sub(r"Explorador (de )?blockchain a fondo: ", "blockchain.info: ", html)

with open("bit2me.html", "w") as file:
    file.write(html)
