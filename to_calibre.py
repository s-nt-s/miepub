#!/usr/bin/python3

import argparse
import os
import sys
import yaml
import re
from subprocess import check_output
from bunch import Bunch
from glob import glob
import shlex

re_nb = re.compile(r"\d+")

def run(*cmd):
    output = check_output(cmd)
    output = output.decode(sys.stdout.encoding)
    return output

def get(search, to_list=False):
    try:
        r = run("calibredb", "search", search)
        if to_list:
            r = [int(i) for i in r.split(",")]
        return r
    except:
        return None

parser = argparse.ArgumentParser(description="Añade archivos a Calibre")
parser.add_argument("config", nargs='?', help="Fichero Yaml de configuración")
parser.add_argument('--example', action='store_true', help='Muestra un fichero de configuración de ejemplo')
args = parser.parse_args()

if args.example:
    print("#!"+os.path.abspath(__file__)+r'''
files: ~/Manga/Black Jack/*.cbr
rem: 'title:"Black Jack #"'
add: calibredb add --isbn 978-84-8357-034-0 --authors "Osamu Tezuka" --series "Black Jack"
serie: "Black Jack #"
mod:
    - calibredb set_custom myshelves {} "Manga"
    - calibredb set_metadata --field publisher:Glénat {}
    '''.rstrip())
    sys.exit()

if not args.config:
    sys.exit("config es obligatorio cuando no se usa --example")

if not os.path.isfile(args.config):
    sys.exit(args.config+" no existe")

with open(args.config, 'r') as f:
    config = yaml.load(f, Loader=yaml.BaseLoader)
    config = Bunch(**config)
    config.path = config.files
    config.files = sorted(glob(os.path.expanduser(config.files)))
    if "exclude" in config:
        config.exclude = sorted(glob(os.path.expanduser(config.exclude)))
        config.exclude = [f for f in config.files if f not in config.exclude]

if not config.files:
    sys.exit(config.path+" no da resultados")

r = get(config.rem)
if r:
    print("Eliminando: "+r)
    run("calibredb", "remove", r)

cmd = shlex.split(config.add)
print("Añadiendo "+config.path)
ids = []
for i, f in enumerate(config.files):
    i = i + 1
    id = run(*(cmd+[f]))
    id = re_nb.findall(id)
    ids.append(id[0])

for m in config.mod:
    print("Modificando "+m)
    for id in ids:
        cmd = m.replace("{}", id)
        cmd = shlex.split(cmd)
        run(*cmd)

if config.serie:
    config.serie = config.serie + "%0" + str(len(str(len(ids)))) + "d"
    print("Numerando serie "+config.serie)
    for i, id in enumerate(ids):
        i = i + 1
        cmd = "calibredb set_metadata --field series_index:%s" % i
        cmd = shlex.split(cmd)
        cmd.append(id)
        run(*cmd)
        cmd = ('calibredb set_metadata --field title:"'+config.serie+'"') % i
        cmd = shlex.split(cmd)
        cmd.append(id)
        run(*cmd)
        cmd = ('calibredb set_metadata --field title_sort:"'+config.serie+'"') % i
        cmd = shlex.split(cmd)
        cmd.append(id)
        run(*cmd)
