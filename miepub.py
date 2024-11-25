#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import filecmp
import glob
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import urllib.request
import zipfile
from subprocess import call, check_output
from shutil import copy

import bs4
import pypandoc
import yaml

parser = argparse.ArgumentParser(
    description='Genera epub')
parser.add_argument("--out", help="Nombre del fichero de salida")
parser.add_argument("--toc", type=int,
                    help="Profundidad del indice", default=2)  # toc-depth
parser.add_argument("--cover", help="Imagen de portada")  # --epub-cover-image
parser.add_argument("--metadata", help="Metadatos del epub")  # --epub-metadata
parser.add_argument("--css", help="Estilos del epub")  # --epub-stylesheet
# --epub-chapter-level
parser.add_argument("--chapter-level", help="Nivel de divisón de capitulos")
parser.add_argument("--txt-cover", help="Crea una portada basada en un texto")
parser.add_argument("--gray", help="Convertir imagenes a blanco y negro",
                    action='store_true', default=False)
parser.add_argument("--trim", help="Recorta los margenes de las imagenes",
                    action='store_true', default=False)
parser.add_argument("--copy-class", help="Copiar el atributo class de la fuente al epub",
                    action='store_true', default=False)
parser.add_argument("--width", type=int, help="Ancho máximo para las imágenes")
parser.add_argument(
    "--notas", help="Nombre del capítulo donde se quieren generar las notas (por defecto se usara el último capítulo)")
parser.add_argument(
    "--execute", help="Ejecuta script sobre el epub antes de empaquetarlo")
parser.add_argument("--keep-title", help="Mantiene la página de título",
                    action='store_true', default=False)
parser.add_argument("fuente", help="Fichero de entrada")

arg = parser.parse_args()

re_sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)
class_name = re.compile(r"\.(\S+)")
tipo_fuente = re.compile(r"^(.*)\.(md|html)$")
if arg.keep_title:
    no_content = re.compile(
        r'<item id="nav" |<itemref idref="nav" |href="nav.xhtml')
else:
    no_content = re.compile(
        r'<item id="nav" |<item id="title_page" |<item id="title_page_xhtml" |<itemref idref="title_page" |<itemref idref="title_page_xhtml" |<itemref idref="nav" |href="nav.xhtml')

if not os.path.isfile(arg.fuente):
    sys.exit(arg.fuente + " no existe")
if not tipo_fuente.match(arg.fuente):
    sys.exit(arg.fuente + " no tiene la extensión adecuada (.md o .html)")
if arg.execute and (not os.path.isfile(arg.execute) or not os.access(arg.execute, os.X_OK)):
    sys.exit(arg.execute + " no es un programa ejecutable")


arg.html = arg.fuente.endswith(".html")
arg.md = arg.fuente.endswith(".md")
arg.fuente = os.path.realpath(arg.fuente)
arg.dir_fuente = os.path.dirname(arg.fuente)

if arg.out:
    arg.out = os.path.realpath(arg.out)
else:
    arg.out = tipo_fuente.sub(r"\1.epub", arg.fuente)

prefix = os.path.basename(tipo_fuente.sub(
    r"\1", arg.fuente)).replace(" ", "_") + "_"

mogrify = ["mogrify"]
if arg.trim:
    mogrify.extend(["-strip", "+repage", "-fuzz", "600", "-trim"])
if arg.gray:
    mogrify.extend(["-colorspace", "GRAY"])
if arg.width:
    mogrify.extend(["-resize", str(arg.width) + ">"])

tag_concat = ['u', 'ul', 'ol', 'i', 'em', 'strong']
tag_round = ['u', 'i', 'em', 'span', 'strong', 'a']
tab_block = ['p', 'li', "tr", "thead", "tbody", 'th', 'td', 'div', 'caption', 'h[1-6]', 'figcaption']


def get_text(n: bs4.Tag):
    if n is None:
        return None
    txt = re_sp.sub(" ", n.get_text()).strip()
    if len(txt) == 0:
        return None
    return txt


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Y', suffix)


def minify_soup(soup):
    def __re(rg: str):
        return re.compile(rg, re.MULTILINE | re.DOTALL | re.UNICODE)

    h = str(soup) # htmlmin.minify(str(soup), remove_empty_space=True)

    for t in tag_concat:
        r = __re(r"</" + t + r">(\s*)<" + t + ">")
        h = r.sub(r"\1", h)
    for t in tag_round:
        for r in (
            __re(r"(<" + t + r">)(\s+)"),
            __re(r"(<" + t + r" [^>]+>)(\s+)"),
            __re(r"(\s+)(</" + t + r">)")
        ):
            h = r.sub(r"\2\1", h)
    for t in tab_block:
        for r in (
            __re(r"\s*(<" + t + r">)\s*"),
            __re(r"\s*(<" + t + r" [^>]+>)\s*"),
        ):
            h = r.sub(r"\n\1", h)
        h = __re(r"\s*(</" + t + r">)\s*").sub(r"\1\n", h)
    return h


def descargar(url, dwn):
    try:
        urllib.request.urlretrieve(url, dwn)
    except:
        call(["wget", url, "--quiet", "-O", dwn])


def simplifica(s):
    s = unicodedata.normalize('NFKD', s)
    s = s.encode('ascii', 'ignore')
    s = s.decode('ascii', 'ignore')
    s = s.strip(".")
    s = s.strip()
    s = s.strip(".")
    s = s.strip()
    return s


def optimizar(s):
    antes = os.path.getsize(s)
    c = tmp_wks + "/" + os.path.basename(s)
    shutil.copy(s, c)
    if len(mogrify) > 1:
        call(mogrify + [c])
    call(["picopt", "--quiet", "--destroy_metadata",
          "--comics", "--enable_advpng", c])
    despues = os.path.getsize(c)
    if antes > despues:
        shutil.move(c, s)


def get_yaml(md):
    with open(md, "r") as f:
        itr = iter(f)
        if next(itr) != '---\n':
            return {}
        yml = ""
        for line in itr:
            if line == '---\n':
                return yaml.load(yml.rstrip(), Loader=yaml.FullLoader)
            yml += line
    return {}


def extra_arguments(extra):
    if not extra:
        return
    if isinstance(extra, bs4.Tag):
        extra = extra.attrs["content"]
    extra = re_sp.sub(" ", extra).strip()
    if len(extra) == 0:
        return
    print("Argumentos extra: "+extra)
    extra = extra.split(" ")
    if '--copy-class' in extra:
        arg.copy_class = True
        extra.remove('--copy-class')
    extra_args.extend(extra)


def str_to_cmd(s):
    arr = []
    flag = True
    for i in s.split('"'):
        flag = not flag
        if flag:
            arr.append(i)
            continue
        i = i.strip()
        for c in i.split():
            arr.append(c)
    return arr


tmp = tempfile.mkdtemp(prefix=prefix)

print("Directorio de trabajo: " + tmp)

tmp_in = tmp + "/in"
tmp_out = tmp + "/out"
tmp_wks = tmp + "/wks"

os.mkdir(tmp_in)
os.mkdir(tmp_out)
os.mkdir(tmp_wks)

clases = []
extra_args = []
yml = {}

if arg.md:
    yml = get_yaml(arg.fuente)
    extra_arguments(yml.get("pandoc", None))

if arg.html:
    with open(arg.fuente, "rb") as f:
        soup = bs4.BeautifulSoup(f, "lxml")
        extra_arguments(soup.find("meta", {"name": "pandoc"}))
        ebook_meta = soup.find("meta", {"name": "ebook-meta"})
        if ebook_meta:
            yml["ebook-meta"] = ebook_meta.attrs["content"]
        txt_cover = soup.find("meta", {"name": "txt_cover"})
        if txt_cover:
            yml["txt-cover"] = txt_cover.attrs["content"]
        if not arg.metadata:
            meta = ""
            for m in soup.findAll("meta", {"name": re.compile(r"^dc\.", re.IGNORECASE)}):
                n = m.attrs["name"].lower()
                c = m.attrs["content"]
                n = "dc:" + n[3:]
                meta += "<%s>%s</%s>\n" % (n, c, n)
            if len(meta) > 0:
                print("Recuperados metadatos del html")
                arg.metadata = tmp_in + "/metadata.xml"
                with open(arg.metadata, "w") as file:
                    file.write(meta)
        if not arg.cover:
            c = soup.find("meta", attrs={'property': "og:image"})
            if c and "content" in c.attrs:
                print("Recuperada portada de los metadatos del html")
                arg.cover = c.attrs["content"]
        if not arg.css:
            c = soup.find("link", attrs={'media': "print"})
            if c and "type" in c.attrs and c.attrs["type"] == "text/css":
                arg.css = c.attrs["href"]
                if not arg.css.startswith("http") and not os.path.isfile(arg.css):
                    dir_fuente = os.path.dirname(arg.fuente)
                    if not arg.css.startswith("/"):
                        dir_fuente = dir_fuente + "/"
                    arg.css = dir_fuente + arg.css
                    arg.css = os.path.realpath(arg.css)
        if arg.css and arg.copy_class:
            with open(arg.css, "r") as c:
                class_names = [c.rstrip(",")
                               for c in class_name.findall(c.read())]
                if len(class_names):
                    class_names = "." + ", .".join(class_names)
                    clases = soup.select(class_names)

if "txt-cover" in yml:
    arg.txt_cover = yml['txt-cover']

if arg.txt_cover:
    print("Creando portada '%s'" % arg.txt_cover)
    arg.cover = tmp_in + "/cover.png"
    call(["convert", "-monochrome", "-gravity", "Center", "-interline-spacing", "40", "-background", "White", "-fill",
          "Black", "-size", "560x760", "caption:%s" % arg.txt_cover, "-bordercolor", "White", "-border", "20x20", arg.cover])

if arg.cover and arg.cover.startswith("http"):
    print("Descargando portada de " + arg.cover)
    _, extension = os.path.splitext(arg.cover)
    dwn = tmp_in + "/cover" + extension
    descargar(arg.cover, dwn)
    arg.cover = dwn

if arg.css and arg.css.startswith("http"):
    print("Descargando css de " + arg.css)
    dwn = tmp_in + "/" + os.path.basename(arg.css)
    descargar(arg.cover, dwn)
    arg.css = dwn

if '--toc-depth' not in extra_args:
    extra_args.extend(['--toc-depth', str(arg.toc)])
if arg.cover and '--epub-cover-image' not in extra_args:
    extra_args.extend(['--epub-cover-image', arg.cover])
if arg.metadata and '--epub-metadata' not in extra_args:
    extra_args.extend(['--epub-metadata', arg.metadata])
if arg.css and '--epub-stylesheet' not in extra_args:
    extra_args.extend(['--epub-stylesheet', arg.css])
if arg.html and '--parse-raw' not in extra_args:
    extra_args.append('--parse-raw')
if arg.chapter_level and '--epub-chapter-level' not in extra_args:
    extra_args.extend(['--epub-chapter-level', arg.chapter_level])


print("Convirtiendo con pandoc")
#print("pandoc "+arg.fuente+" "+ " ".join(str(i) for i in extra_args)+" -o ")
pypandoc.convert_file(arg.fuente,
                      outputfile=arg.out,
                      to="epub",
                      extra_args=extra_args)

print("Epub inicial de " + sizeof_fmt(os.path.getsize(arg.out)))

copy(arg.out, tmp)

print("Descomprimiendo epub")
with zipfile.ZipFile(arg.out, 'r') as zip_ref:
    zip_ref.extractall(tmp_out)
    zip_ref.close()

print("Eliminando navegación inecesaria")
os.remove(tmp_out + "/nav.xhtml")
if arg.keep_title:
    with open(tmp_out + "/title_page.xhtml", "r") as f:
        tt_soup = bs4.BeautifulSoup(f, "xml")
    n_body = tt_soup.new_tag("body")
    o_body = tt_soup.find("body")
    for a in o_body.attrs:
        n_body[a] = o_body.attrs[a]
    o_body.name = "div"
    o_body.attrs.clear()
    o_body.attrs["class"] = "title_page"
    o_body.wrap(n_body)
    with open(tmp_out + "/title_page.xhtml", "w") as f:
        f.write(str(tt_soup))
else:
    os.remove(tmp_out + "/title_page.xhtml")

with open(tmp_out + "/content.opf", "r+") as f:
    d = "".join(l for l in f.readlines() if not no_content.search(l))
    if isinstance(yml.get('date'), int):
        d = re.sub(r"<dc:date>[^<]+</dc:date>", f"<dc:date>{yml['date']}</dc:date>", d)
    f.seek(0)
    f.write(d)
    f.truncate()

marcas = {}

with open(tmp_out + "/toc.ncx", "r+") as f:
    soup = bs4.BeautifulSoup(f, "xml")
    nav = soup.find("navMap")
    nav.find("navPoint").extract()
    for c in nav.select("content"):
        antes = c.attrs["src"]
        despues = simplifica(antes)
        if antes != despues:
            c.attrs["src"] = despues
            despues = despues.split("#", 1)[-1]
            antes = antes.split("#", 1)[-1]
            marcas[antes] = despues
    f.seek(0)
    f.write(str(soup))
    f.truncate()

media = tmp_out + "/media/"
imgs = []
for g in ['*.jpeg', '*.jpg', '*.png']:
    imgs.extend(glob.glob(media + g))
imgdup = {}
i = 0
while i < len(imgs) - 1:
    c = imgs[i]
    dup = [x for x in imgs[i + 1:] if filecmp.cmp(x, c)]
    c = "media/" + os.path.basename(c)
    for d in dup:
        imgs.remove(d)
        os.remove(d)
        d = "media/" + os.path.basename(d)
        imgdup[d] = c
    i += 1

if imgdup:
    re_keys = [re.escape(k) for k in imgdup.keys()]
    re_imgdup = re.compile("href=\"(" + "|".join(re_keys) + ")\"")
    with open(tmp_out + "/content.opf", "r+") as f:
        d = [l for l in f.readlines() if not re_imgdup.search(l)]
        f.seek(0)
        f.write("".join(d))
        f.truncate()
    print("Eliminadas imagenes duplicadas")

xhtml = sorted(glob.glob(tmp_out + "/ch*.xhtml"))
notas = []
xnota = os.path.basename(xhtml[-1])
count = 1

if arg.notas:
    for html in xhtml:
        with open(html, "r+") as f:
            soup = bs4.BeautifulSoup(f, "xml")
            if soup.find("h1", text=arg.notas):
                xnota = os.path.basename(html)
                break


if os.path.isfile(tmp_out + "/nav.xhtml"):
    with open(tmp_out + "/nav.xhtml", "r+") as f:
        soup = bs4.BeautifulSoup(f, "xml")
        for a in soup.findAll("a"):
            href=a.attrs.get("href")
            if a and "#" in href:
                href, antes = href.rsplit("#", 1)
                despues = simplifica(antes)
                if despues and antes!=despues:
                    a.attrs["href"] = href + "#" + despues
        minified = minify_soup(soup)
        f.seek(0)
        f.write(minified)
        f.truncate()

fixNotas = {}
for html in xhtml:
    chml = os.path.basename(html)
    with open(html, "r+") as f:
        soup = bs4.BeautifulSoup(f, "xml")
        for c in soup.select("div"):
            if "id" in c.attrs and c.attrs["id"] in marcas:
                c.attrs["id"] = marcas[c.attrs["id"]]
        for ids in soup.select("*[id]"):
            antes = ids.attrs["id"]
            despues = simplifica(antes)
            if despues and antes!=despues:
                ids.attrs["id"] = despues
        for p in soup.select("table p") + soup.select("figure p"):
            p.unwrap()
        for i in soup.select("img"):
            if "src" in i.attrs and i.attrs["src"] in imgdup:
                i.attrs["src"] = imgdup[i.attrs["src"]]
        if chml != xnota:
            footnotes = soup.find("div", attrs={'class': "footnotes"})
            if footnotes:
                bak_count = count
                for p in footnotes.findAll("p"):
                    a = p.select("a")[-1]
                    if a['href'].startswith("#"):
                        a['href'] = chml + a['href']
                    p['id'] = "fn" + str(count)
                    sup = soup.new_tag("sup")
                    sup.string = "[" + str(count) + "]"
                    p.insert(0, sup)
                    p.insert(1, " ")
                    a['class'] = "volver"
                    a.insert_before(" ")
                    a.string = "<<"
                    notas.append(p)
                    count = count + 1
                footnotes.extract()
                count = bak_count
                for a in soup.findAll("a", attrs={'class': "footnoteRef"}):
                    a['href'] = xnota + "#fn" + str(count)
                    sup = a.find("sup")
                    if not sup:
                        sup = soup.new_tag("sup")
                        a.string = ""
                        a.append(sup)
                    sup.string = "[" + str(count) + "]"
                    if a.previous_sibling is None:
                        raise Exception(str(a)+" previous_sibling = None")
                    if len(a.previous_sibling.string) > 0 and len(a.previous_sibling.strip()) == 0:
                        a.previous_sibling.extract()
                    count = count + 1
            else:
                for a in soup.findAll("a", attrs={'class': "footnoteRef"}):
                    if a['href'].startswith("#"):
                        a['href'] = xnota + a['href']
                        fixNotas[a['id']] = chml
        else:
            div = soup.find("div")
            for n in notas:
                div.append(n)
            for _id, xml in fixNotas.items():
                a = div.find("a", attrs={"href": "#"+_id})
                if a:
                    a.attrs["href"] = xml + a.attrs["href"]

        for c in clases:
            fnd = soup.find(lambda t: t.name == c.name and re_sp.sub(
                " ", t.get_text()).strip() == re_sp.sub(" ", c.get_text()).strip())
            if fnd and "class" not in fnd.attrs:
                fnd.attrs["class"] = c.attrs["class"]

        for img in soup.findAll("img"):
            if "alt" not in img.attrs:
                img.attrs["alt"]=""

        for n in soup.findAll("article"):
            n.name = "div"

        if arg.md:
            for tr in soup.select("tr"):
                if "class" in tr:
                    del tr.attrs["class"]
                colspan = 0
                td: bs4.Tag
                for td in tr.findAll(["td", "th"]):
                    if get_text(td) == ">":
                        colspan = colspan + 1
                        td.extract()
                    elif colspan > 0:
                        td.attrs["colspan"] = str(colspan+1)
                        td.attrs["style"] = "text-align: center;"
                        colspan = 0
            for td in soup.findAll(["td", "th"]):
                b = td.select_one("strong")
                if b and get_text(b) == get_text(td):
                    b.unwrap()
                    td.name = "th"
            for tbody in soup.select("tbody"):
                trs = list(tbody.select("tr"))
                for i, tr in enumerate(trs):
                    if any(map(get_text, tr.select("td"))):
                        continue
                    if tr != tbody.find("tr"):
                        tbd = soup.new_tag('tbody')
                        tbody.insert_after(tbd)
                        for _tr in trs[i:]:
                            tbd.append(_tr)
                    tbody: bs4.Tag = tr.find_parent("tbody")
                    thead = tbody.find_previous_sibling()
                    while not (thead and isinstance(thead, bs4.Tag)):
                        thead = thead.find_previous_sibling()
                    if thead is None or thead.name != "thead":
                        thead = soup.new_tag('thead')
                        tbody.insert_before(thead)
                    for td in tr.select("td"):
                        td.name = "th"
                    thead.append(tr)
            for tbody in soup.findAll(["thead", "tbody"]):
                for i, tr in enumerate(tbody.select("tr")):
                    tr.attrs["class"] = "odd" if (i % 2) == 0 else "even"
            for c in soup.findAll("cite"):
                p = c.parent
                q = p.parent
                if q.name == "blockquote" and p.name == "p" and re_sp.sub(" ", p.get_text()).strip() == re_sp.sub(" ", c.get_text()).strip():
                    p.attrs["class"] = "cite"
                    q.attrs["class"] = "cite"

        minified = minify_soup(soup)
        f.seek(0)
        f.write(minified)
        f.truncate()

if arg.gray or arg.width or arg.trim and len(imgs) > 0:
    print("Limpiando imagenes")
    antes = sum(map(os.path.getsize, imgs))
    call(["exiftool", "-r", "-overwrite_original", "-q", "-all=", media])
    despu = sum(map(os.path.getsize, imgs))
    print("Ahorrado borrando exif: " + sizeof_fmt(antes - despu))
    imgs = sorted(imgs)
    for img in imgs:
        optimizar(img)
    despu = despu - sum([os.path.getsize(s) for s in imgs])
    if despu > 0:
        print("Ahorrado optimizando: " + sizeof_fmt(despu))

if arg.execute:
    call([arg.execute, tmp_out, arg.fuente])

with zipfile.ZipFile(arg.out, "w") as zip_file:
    zip_file.write(tmp_out + '/mimetype', 'mimetype',
                   compress_type=zipfile.ZIP_STORED)
    z = len(tmp_out) + 1
    for root, dirs, files in os.walk(tmp_out):
        for f in files:
            path = os.path.join(root, f)
            name = path[z:]
            if name != 'mimetype':
                zip_file.write(path, name, compress_type=zipfile.ZIP_DEFLATED)

if yml:
    metadata = []
    if len(yml.get("tags", [])) > 0:
        tags = "," .join(yml.get("tags"))
        metadata.extend(["--tags", tags])
    if yml.get("category", False):
        metadata.extend(["--category", yml.get("category")])
    if "ebook-meta" in yml:
        metadata.extend(str_to_cmd(yml["ebook-meta"]))
    if len(metadata) > 0:
        check_output(["ebook-meta"] + metadata + [arg.out])

print("Epub final de " + sizeof_fmt(os.path.getsize(arg.out)))
