#!/usr/bin/env python3

import re

import bs4
import requests
from bunch import Bunch

from limpiar import Limpiar, heads, vacio

sp = re.compile(r"\s+")

ban_imgs = [i.strip()
            for i in open("imgs.txt").readlines() if len(i.strip()) > 0]

idc = 0
ids = {}


def get(url):
    r = requests.get(url)
    return bs4.BeautifulSoup(r.content, "lxml")


def append(body, li, nivel):
    global idc
    global ids

    a = li.find("a")
    h = out.new_tag("h"+str(nivel))
    h.string = a.get_text()

    idc += 1
    _id = "mrk" + str(idc)
    h.attrs["id"] = _id
    body.append(h)
    url = a.attrs["href"]
    ids[url] = h

    if url != "#":
        soup = get(url)
        div = soup.find("div", attrs={"class": "entry-content"})
        div.attrs.clear()
        div.name = "article"
        div = lmp.check_heads(nodo=div, inicio=2)  # nivel)
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
''', 'lxml')

lmp = Limpiar(out, noscript=True, iframe_to_anchor=True, resolve_images=True,
              clear_attr=heads + ["p", "figure", "ul", "ol", "img", "a"])

body = out.body

libro = []

lis = soup.select("aside ul.menu > li")[1:]
for li in lis:
    append(body, li, 1)
    for l in li.findAll("li"):
        append(body, l, 2)

lmp.limpiar()
out = lmp.soup

for c in ".rt-reading-time, .share-before, .tm-click-to-tweet, .tm-tweet-clear".split(", "):
    for s in out.select(c):
        s.extract()

for a in out.findAll("a", attrs={"href": re.compile(r"https?://blog.bit2me.com/es/guia-bitcoin/?")}):
    a.unwrap()

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

for i in out.findAll("img"):
    if i.attrs["src"] in ban_imgs:
        p = i.parent
        t = sp.sub("", p.get_text()).strip()
        if p.name == "figure" or (p.name == "p" and len(t) == 0):
            p.extract()
        else:
            i.extract()

for i in out.findAll("span"):
    st = i.attrs.get("style", None)
    if st:
        i.attrs.clear()
        i.attrs["style"] = st
    else:
        i.unwrap()

for a in out.findAll("a"):
    url = a.attrs["href"]
    if url in ids:
        h = ids[url]
        i = h.get_text().split(" ")[0].strip()
        i = re.sub(r"\.$", "", i)
        a.attrs.clear()
        a.attrs["href"] = "#" + h.attrs["id"]
        a.insert(0, " ")
        span = out.new_tag("span")
        span.attrs["class"] = "mark"
        span.string = "[" + i + "]"
        a.insert(0, span)

lmp.load(out)
lmp.limpiar()
out = lmp.soup

imgs = []
for i in out.findAll("img"):
    src = i.attrs["src"]
    alt = i.attrs.get("alt", src.split("/")[-1])
    if src in imgs and src != "http://blog.bit2me.com/es/wp-content/uploads/sites/2/2016/01/informacion_transaccion.png":
        i.extract()
    else:
        i.attrs.clear()
        i.attrs = {
            "src": src,
            "alt": alt
        }
    imgs.append(src)

for h in out.findAll(heads):
    p = h.parent
    if p and p.name == "li":
        h.unwrap()
    else:
        a, b = sibling(h)
        if b and b.name.startswith("h") and int(b.name[1]) <= int(h.name[1]):
            h.name = "p"

lmp.load(out)
lmp.limpiar()

html = lmp.html
html = re.sub(r"Explorador (de )?blockchain a fondo: ",
              "blockchain.info: ", html)

with open("bit2me.html", "w") as file:
    file.write(html)
