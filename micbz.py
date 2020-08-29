#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import filecmp
from glob import iglob
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import urllib.request
import zipfile
import rarfile
from subprocess import call, check_output
from PIL import Image

import bs4
import htmlmin
import pypandoc
import yaml
from PIL import Image

ban_file=re.split(r"\s*\n\s*", '''
SelloDragón_.jpg
zz_portadilla final.jpg
Gunnm-*_002.jpg
Gunnm-*_003.jpg
Gunnm-*_005.jpg
Gunnm-*_006.jpg
*.txt
'''.strip())

def rm_ban_files(target):
    for glb in ban_file:
        for f in iglob(target+"/**/"+glb, recursive=True):
            os.remove(f)

def _extract(fl, target):
    ext = fl.split(".")[-1].lower()
    if ext in ("cbz", "zip"):
        with zipfile.ZipFile(fl, 'r') as zip_ref:
            zip_ref.extractall(target)
            zip_ref.close()
        return True
    if ext in ("cbr", "rar"):
        with rarfile.RarFile(fl, 'r') as rar_ref:
            rar_ref.extractall(target)
            rar_ref.close()
        return True
    return False

def extract(fl, target):
    if os.path.isdir(fl):
        os.makedirs(target, exist_ok=True)
        target = target + '/' + os.path.basename(fl)
        print(fl, "->", target)
        shutil.copytree(fl, target)
        return target
    if not _extract(fl, target):
        return False
    while True:
        fls = os.listdir(target)
        if len(fls)!=1:
            return target
        fls = os.path.join(target, fls[0])
        if not os.path.isdir(fls):
            return target
        target=fls
    return target

def build(tmp_out, target):
    target = target+".cbz"
    if os.path.isfile(target):
        os.remove(target)
    with zipfile.ZipFile(target, "w") as zip_file:
        #rar_file.write(tmp_out + '/mimetype', 'mimetype', compress_type=zipfile.ZIP_STORED)
        z = len(tmp_out) + 1
        for root, dirs, files in os.walk(tmp_out):
            for f in files:
                path = os.path.join(root, f)
                name = path[z:]
                if name != 'mimetype':
                    zip_file.write(path, name, compress_type=zipfile.ZIP_DEFLATED)


def get_files(target):
    for r, d, f in os.walk(target):
        for file in f:
            yield os.path.join(r, file), file.lower()

def call_mogrify(fl, *arg):
    call(["mogrify"] + list(arg) + [fl])

parser = argparse.ArgumentParser(description='Optimiza cbr/cbz')
parser.add_argument("--out", type=str, help="Directorio de sálida", default=".")
parser.add_argument("--width", type=int, help="Ancho máximo", default=1072)
parser.add_argument("--height", type=int, help="Alto máximo", default=1448)
parser.add_argument("--serie", action='store_true', help="Indica que es una serie", default=True)
parser.add_argument("origen", nargs='+', help="Ficheros de origen")

arg = parser.parse_args()

if not os.path.isdir(arg.out):
    sys.exit(arg.out+" no es un directorio")
    if not arg.out.endswith("/"):
        out = out + "/"

origen=[]
for f in arg.origen:
    if os.path.isdir(f):
        origen.append(f.rstrip("/"))
        continue
    if not os.path.isfile(f):
        sys.exit(f+" no es un fichero")
    ext = f.split(".")[-1].lower()
    if ext not in ("cbr", "cbz", "rar", "zip"):
        print(f, "se ignorará")
        continue
    origen.append(f)

if not origen:
    sys.exit("No hay cbr/cbz de origen")
arg.origen=sorted(origen)
arg.serie_name = os.path.basename(os.path.realpath(arg.out)) + " #%0" + (str(len(str(len(arg.origen))))) + "d"

mogrify = ["-strip", "+repage", "-bordercolor", "None", "-fuzz", "30%", "-trim", "-resize", str(arg.width) + ">"]
tmp = "/tmp/micbz" #tempfile.mkdtemp()
print("cd " + tmp)
for i, cbr in enumerate(arg.origen):
    print(os.path.basename(cbr))
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp)
    wks = extract(cbr, tmp)
    rm_ban_files(tmp)
    print('cd "%s"' % wks)
    for fl, name in get_files(wks):
        ext = name.split(".")[-1]
        if ext in ("jpg"):
            ancho, alto = Image.open(fl).size
            if ancho > alto:
                call_mogrify(fl, "-rotate", "90", *mogrify[1:])
            else:
                call_mogrify(fl, *mogrify)
            ancho, alto = Image.open(fl).size
            if ancho<5:
                os.remove(fl)
    if arg.serie:
        out = arg.serie_name % (i+1)
    else:
        out = os.path.join(arg.out, os.path.basename(cbr))[:-4]
    build(wks, out)
