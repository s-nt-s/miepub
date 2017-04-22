#!/usr/bin/python3
# -*- coding: utf-8 -*-

import zipfile
import bs4
import tempfile
import os
import glob
import shutil
import pypandoc
import argparse
import re
import tempfile
import shutil
import urllib.request
import pypandoc
import zipfile
import unicodedata
import filecmp
import htmlmin
from subprocess import call, check_output
from PIL import Image
import sys

parser = argparse.ArgumentParser(
    description='Genera epub')
parser.add_argument("--out", help="Nombre del fichero de salida")
parser.add_argument("--toc", type=int, help="Profundidad del indice", default=2) # toc-depth
parser.add_argument("--cover", help="Imagen de portada") # --epub-cover-image
parser.add_argument("--metadata", help="Metadatos del epub") # --epub-metadata
parser.add_argument("--css", help="Estilos del epub") # --epub-stylesheet
parser.add_argument("--gray", help="Convertir imagenes a blanco y negro", action='store_true', default=False)
parser.add_argument("--trim", help="Recorta los margenes de las imagenes", action='store_true', default=False)
parser.add_argument("--width", type=int, help="Ancho máximo para las imagenes")
parser.add_argument("--execute", help="Ejecuta script sobre el epub antes de empaquetarlo")
parser.add_argument("fuente", help="Fichero de entrada")

arg = parser.parse_args()

sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)
tipo_fuente = re.compile(r"^(.*)\.(md|html)$")
no_content= re.compile(r'<item id="nav" |<item id="title_page" |<item id="title_page_xhtml" |<itemref idref="title_page" |<itemref idref="title_page_xhtml" |<itemref idref="nav" |href="nav.xhtml')

if not os.path.isfile(arg.fuente):
    sys.exit(arg.fuente+" no existe")
if not tipo_fuente.match(arg.fuente):
    sys.exit(arg.fuente+" no tiene la extensión adecuada (.md o .html)")
if arg.execute and (not os.path.isfile(arg.execute) or not os.access(arg.execute, os.X_OK)):
    sys.exit(arg.execute+" no es un programa ejecutable")

# = os.getcwd()
arg.fuente=os.path.realpath(arg.fuente)
arg.dir_fuente = os.path.dirname(arg.fuente)

if arg.out:
    arg.out=os.path.realpath(arg.out)
else:
    arg.out=tipo_fuente.sub(r"\1.epub", arg.fuente)

prefix = os.path.basename(tipo_fuente.sub(r"\1", arg.fuente)).replace(" ","_")+"_"

mogrify=["mogrify"]
if arg.trim:
    mogrify.extend(["-strip", "+repage", "-trim", "-fuzz", "600"])
if arg.gray:
    mogrify.extend(["-colorspace", "GRAY"])
if arg.width:
    mogrify.extend(["-resize", str(arg.width)+">"])

def sizeof_fmt(num, suffix='B'):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Y', suffix)

tmp = tempfile.mkdtemp(prefix=prefix)

print ("Directorio de trabajo: "+tmp)

tmp_in=tmp+"/in"
tmp_out=tmp+"/out"
tmp_wks=tmp+"/wks"

os.mkdir(tmp_in)
os.mkdir(tmp_out)
os.mkdir(tmp_wks)

if arg.fuente.endswith(".html"):
    with open(arg.fuente,"rb") as f:
        soup = bs4.BeautifulSoup(f, "lxml")
        if not arg.metadata:
            meta = ""
            for m in soup.select("meta"):
                if "name" in m.attrs and "content" in m.attrs:
                    n=m.attrs["name"].lower()
                    c=m.attrs["content"]
                    if n.startswith("dc."):
                        n="dc:"+n[3:]
                        meta += "<%s>%s</%s>\n" % (n, c, n)
            if len(meta)>0:
                print ("Recuperados metadatos del html")
                arg.metadata=tmp_in+"/metadata.xml"
                with open(arg.metadata, "w") as file:
                    file.write(meta)
        if not arg.cover:
            c = soup.find("meta", attrs={'property': "og:image"})
            if c and "content" in c.attrs:
                print ("Recuperada portada de los metadatos del html")
                arg.cover = c.attrs["content"]
        if not arg.css:
            c = soup.find("link", attrs={'media': "print"})
            if c and "type" in c.attrs and c.attrs["type"]  == "text/css":
                arg.css = c.attrs["href"]

def descargar(url, dwn):
    try:
        urllib.request.urlretrieve(url, dwn)
    except:
        call(["wget",url,"--quiet", "-O",dwn])

if arg.cover and arg.cover.startswith("http"):
    print ("Descargando portada de "+arg.cover)
    _ , extension = os.path.splitext(arg.cover)
    dwn = tmp_in+"/cover"+extension
    descargar(arg.cover, dwn)
    arg.cover=dwn

if arg.css and arg.cover.startswith("http"):
    print ("Descargando css de "+arg.css)
    dwn = tmp_in+"/"+os.path.basename(arg.css)
    descargar(arg.cover, dwn)
    arg.css=dwn

extra_args=['--toc-depth', str(arg.toc)]
if arg.cover:
    extra_args.extend(['--epub-cover-image', arg.cover])
if arg.metadata:
    extra_args.extend(['--epub-metadata', arg.metadata])
if arg.css:
    extra_args.extend(['--epub-stylesheet', arg.css])
if arg.fuente.endswith(".html"):
    extra_args.append('--parse-raw')
    

print ("Convirtiendo con pandoc")
pypandoc.convert_file(arg.fuente,
    outputfile=arg.out,
    to="epub",
    extra_args=extra_args)

print ("Epub inicial de " + sizeof_fmt(os.path.getsize(arg.out)))

print ("Descomprimiendo epub")
with zipfile.ZipFile(arg.out, 'r') as zip_ref:
    zip_ref.extractall(tmp_out)
    zip_ref.close()

print ("Eliminando navegación inecesaria")
os.remove(tmp_out+"/nav.xhtml")
os.remove(tmp_out+"/title_page.xhtml")

with open(tmp_out+"/content.opf","r+") as f:
    d = [l for l in f.readlines() if not no_content.search(l)]
    f.seek(0)
    f.write("".join(d))
    f.truncate()

def simplifica(s):
    return unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii','ignore')

marcas = {}

with open(tmp_out+"/toc.ncx","r+") as f:
    soup = bs4.BeautifulSoup(f, "xml")
    nav = soup.find("navMap")
    nav.find("navPoint").extract()
    for c in nav.select("content"):
        antes=c.attrs["src"]
        despues=simplifica(antes)
        if antes != despues:
            c.attrs["src"]=despues
            despues=despues.split("#",1)[-1]
            antes=antes.split("#",1)[-1]
            marcas[antes]=despues
    f.seek(0)
    f.write(str(soup))
    f.truncate()

xhtml = sorted(glob.glob(tmp_out+"/ch*.xhtml"))
notas = []
xnota = os.path.basename(xhtml[-1])
count = 1

for html in xhtml:
    chml = os.path.basename(html)
    with open(html,"r+") as f:
        soup = bs4.BeautifulSoup(f, "xml")
        for c in soup.select("div"):
            if "id" in c.attrs and c.attrs["id"] in marcas:
                c.attrs["id"]=marcas[c.attrs["id"]]
        for p in soup.select("table p, figure p"):
            p.unwrap()
        if chml != xnota:
            footnotes=soup.find("div", attrs={'class': "footnotes"})
            if footnotes:
                for p in footnotes.findAll("p"):
                    a=p.select("a")[-1]
                    if a['href'].startswith("#"):
                        a['href']=chml+a['href']
                    p['id']="fn"+str(count)
                    sup = soup.new_tag("sup")
                    sup.string="["+str(count)+"]"
                    p.insert(0,sup)
                    p.insert(1," ")
                    a['class']="volver"
                    a.insert_before(" ")
                    a.string="<<"
                    notas.append(p)
                footnotes.extract()
                for a in soup.findAll("a", attrs={'class': "footnoteRef"}):
                    a['href']=xnota+"#fn"+str(count)
                    sup = a.find("sup")
                    if not sup:
                        sup = soup.new_tag("sup")
                        a.string= ""
                        a.append(sup)
                    sup.string="["+str(count)+"]"
                    if len(a.previous_sibling.string)>0 and len(a.previous_sibling.strip())==0:
                        a.previous_sibling.extract()
                    count=count+1
        else:
            div = soup.find("div")
            for n in notas:
                div.append(n)
            
        minified = htmlmin.minify(str(soup), remove_empty_space=True)
        f.seek(0)
        f.write(minified)
        f.truncate()

media = tmp_out+"/media/"
imgs = []
if arg.gray or arg.width or arg.trim:
    for g in ['*.jpeg', '*.jpg', '*.png']:
        imgs.extend(glob.glob(media+g))

def optimizar(s):
    antes = os.path.getsize(s)
    c = tmp_wks+"/"+os.path.basename(s)
    shutil.copy(s, c)
    if len(mogrify)>1:
        call(mogrify + [c])
    call(["picopt", "--quiet", "--destroy_metadata", "--comics", "--enable_advpng", c])
    despues = os.path.getsize(c)
    if antes>despues:
        shutil.move(c, s)

if len(imgs)>0:
    print ("Limpiando imagenes")
    antes = sum(map(os.path.getsize, imgs))
    call(["exiftool", "-r", "-overwrite_original", "-q", "-all=", media])
    despu = sum(map(os.path.getsize, imgs))
    print ("Ahorrado borrando exif: " + sizeof_fmt(antes - despu))
    imgs = sorted(imgs)
    for img in imgs:
        optimizar(img)
    despu = despu - sum([os.path.getsize(s) for s in imgs])
    if despu>0:
        print ("Ahorrado optimizando: " + sizeof_fmt(despu))

if arg.execute:
    call([arg.execute, tmp_out, arg.fuente])

with zipfile.ZipFile(arg.out, "w", zipfile.ZIP_DEFLATED) as zip_file:
    z=len(tmp_out)+1
    for root, dirs, files in os.walk(tmp_out):
        for f in files:
            path = os.path.join(root, f)
            zip_file.write(path,path[z:])

print ("Epub final de " + sizeof_fmt(os.path.getsize(arg.out)))
