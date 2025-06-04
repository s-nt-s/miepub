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
from datetime import date, datetime
from functools import cached_property
from typing import Union, NamedTuple, List, Tuple, Dict

from PIL import Image, ImageDraw, ImageFont
import textwrap

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
parser.add_argument("--chapter-level", help="Nivel de división de capítulos")
parser.add_argument("--txt-cover", help="Crea una portada basada en un texto")
parser.add_argument("--extract", help="Selector de tags a extraer (es decir, borrar)")
parser.add_argument("--gray", help="Convertir imágenes a blanco y negro",
                    action='store_true', default=False)
parser.add_argument("--trim", help="Recorta los margenes de las imágenes",
                    action='store_true', default=False)
parser.add_argument("--copy-class", help="Copiar el atributo class de la fuente al epub",
                    action='store_true', default=False)
parser.add_argument("--width", type=int, help="Ancho máximo para las imágenes")
parser.add_argument(
    "--notas", default="Notas", help="Nombre del capítulo donde se quieren generar las notas (por defecto se usara el último capítulo)")
parser.add_argument(
    "--execute", help="Ejecuta script sobre el epub antes de empaquetarlo")
parser.add_argument("--keep-title", help="Mantiene la página de título",
                    action='store_true', default=False)
parser.add_argument("fuente", help="Fichero de entrada")

re_sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)


class MyDir(NamedTuple):
    root: str
    wks: str
    source: str
    out: str


class MetaData:
    def __init__(self, arg: argparse.Namespace):
        self.__arg = arg
        if not os.path.isfile(self.fuente):
            sys.exit(self.fuente + " no existe")
        if self.ext not in ("md", "html"):
            sys.exit(self.fuente + " no tiene la extensión adecuada (.md o .html)")
        if self.execute and (not os.path.isfile(self.execute) or not os.access(self.execute, os.X_OK)):
            sys.exit(self.execute + " no es un programa ejecutable")

    @cached_property
    def tmp(self):
        tmp = tempfile.mkdtemp(prefix=self.prefix)
        print("Directorio de trabajo: " + tmp)
        tmp_in = tmp + "/in"
        tmp_out = tmp + "/out"
        tmp_wks = tmp + "/wks"
        os.mkdir(tmp_in)
        os.mkdir(tmp_out)
        os.mkdir(tmp_wks)
        return MyDir(
            root=tmp,
            wks=tmp_wks,
            source=tmp_in,
            out=tmp_out,
        )

    @cached_property
    def ext(self):
        return self.fuente.rsplit(".", 1)[-1].lower()

    @cached_property
    def filename(self):
        return self.fuente.rsplit(".", 1)[0]

    @cached_property
    def dir_fuente(self):
        return os.path.dirname(self.fuente)

    @cached_property
    def out(self):
        if self.__arg.out:
            return os.path.realpath(self.__arg.out)
        return self.filename + ".epub"

    @property
    def keep_title(self) -> bool:
        return self.__arg.keep_title

    @cached_property
    def fuente(self) -> str:
        return os.path.realpath(self.__arg.fuente)

    @property
    def execute(self) -> str:
        return self.__arg.execute

    @cached_property
    def re_no_content(self):
        if self.keep_title:
            return None
        return re.compile(r'<item id="title_page" |<item id="title_page_xhtml" |<itemref idref="title_page" |<itemref idref="title_page_xhtml"')

    @cached_property
    def isHtml(self):
        return self.fuente.endswith(".html")

    @cached_property
    def isMd(self):
        return self.fuente.endswith(".md")

    @cached_property
    def prefix(self):
        return os.path.basename(self.filename).replace(" ", "_") + "_"

    @property
    def trim(self) -> bool:
        return self.__arg.trim

    @property
    def gray(self) -> bool:
        return self.__arg.gray

    @property
    def width(self) -> int:
        return self.__arg.width

    @cached_property
    def mogrify(self):
        mogrify = ["mogrify"]
        if self.trim:
            mogrify.extend(["-strip", "+repage", "-fuzz", "600", "-trim"])
        if self.gray:
            mogrify.extend(["-colorspace", "GRAY"])
        if self.width:
            mogrify.extend(["-resize", str(self.width) + ">"])
        return tuple(mogrify)

    @cached_property
    def copy_class(self) -> bool:
        if self.__arg.copy_class:
            return True
        if '--copy-class' in self._extra_arguments:
            return True
        return False

    def get_class_copy_nodes(self) -> Tuple[bs4.Tag, ...]:
        if not self.isHtml:
            return tuple()
        if not self.copy_class:
            return tuple()
        if not self.file_css or not os.path.isfile(self.file_css):
            return tuple()
        with open(self.file_css, "r") as f:
            mth: List[str] = re.findall(r"\.(\S+)", f.read())
            class_names = [c.rstrip(",") for c in mth]
            if len(class_names) == 0:
                return tuple()
            class_names = "." + ", .".join(class_names)
            return tuple(self._soup.select(class_names))

    @cached_property
    def _yml(self) -> dict:
        if not self.isMd:
            return {}
        with open(self.fuente, "r") as f:
            itr = iter(f)
            if next(itr) != '---\n':
                return {}
            yml = ""
            for line in itr:
                if line == '---\n':
                    return yaml.load(yml.rstrip(), Loader=yaml.FullLoader)
                yml += line
        return {}

    @cached_property
    def _soup(self):
        if not self.isHtml:
            return bs4.BeautifulSoup('<xml></xml>', "lxml")
        with open(self.fuente, "rb") as f:
            return bs4.BeautifulSoup(f, "lxml")

    def _get_meta_content(self, name: str) -> Union[str, None]:
        n = self._soup.find("meta", {"name": name})
        if n is None:
            return None
        txt = n.attrs.get("content")
        if txt is None:
            return None
        txt = re_sp.sub(" ", txt).strip()
        if len(txt) == 0:
            return None
        return txt

    @cached_property
    def _extra_arguments(self):
        extra = self._yml.get("pandoc") or self._get_meta_content("pandoc")
        if extra is None:
            return ()
        print("Argumentos extra: "+extra)
        extra = extra.split(" ")
        return tuple(extra)

    @cached_property
    def cover_txt(self) -> Union[str, None]:
        return self._yml.get('txt-cover') or self._get_meta_content('txt_cover')

    @cached_property
    def author(self):
        author = self._yml.get('author')
        if author:
            return author
        creator = self._yml.get('creator')
        if not isinstance(creator, list):
            return None
        authors = [a['text'] for a in creator if a['role'] == 'author']
        if len(authors) == 0:
            return None
        return ", ".join(authors)

    @cached_property
    def file_cover_image(self) -> Union[str, None]:
        file = self.__get_file_cover_image()
        if not (file or "").startswith("http"):
            return file
        print("Descargando portada de " + file)
        _, extension = os.path.splitext(file)
        dwn = self.tmp.source + "/cover" + extension
        descargar(file, dwn)
        return dwn

    def __get_file_cover_image(self) -> Union[str, None]:
        if self.__arg.cover:
            return self.__arg.cover
        c = self._soup.find("meta", attrs={'property': "og:image"})
        if c and "content" in c.attrs:
            print("Recuperada portada de los metadatos del html")
            return c.attrs["content"]

        if self.cover_txt:
            print(f"Creando portada '{self.cover_txt}'")
            return generate_cover(self.cover_txt, output_path=self.tmp.source + "/cover.png")
        if self._yml.get('cover-image'):
            return None
        title = self._yml.get('title')
        if title is None:
            return None
        print("Creando portada desde metadatos")
        return generate_cover(
            title,
            author=self.author,
            date_text=self._yml.get('cover-date') or self._yml.get('date'),
            avatar=self.cover_avatar,
            output_path=self.tmp.source + "/cover.png"
        )

    @cached_property
    def ebook_meta(self) -> Tuple[str, ...]:
        ebook_meta = self._yml.get('ebook-meta') or self._get_meta_content('ebook-meta')
        tags = self._yml.get("tags", [])
        category = self._yml.get('category')
        metadata = []
        if len(tags) > 0:
            metadata.extend(["--tags", "," .join(tags)])
        if category:
            metadata.extend(["--category", category])
        if ebook_meta:
            metadata.extend(str_to_cmd(ebook_meta))
        return tuple(metadata)

    @cached_property
    def file_metadata(self) -> Union[str, None]:
        meta = []
        m: bs4.Tag
        for m in self._soup.findAll("meta", {"name": re.compile(r"^dc\.", re.IGNORECASE)}):
            n = m.attrs["name"].lower()
            c = m.attrs["content"]
            n = "dc:" + n[3:]
            meta.append(f"<{n}>{c}</{n}>")
        if len(meta) == 0:
            return None
        print("Recuperados metadatos del html")
        file = self.tmp.source + "/metadata.xml"
        with open(file, "w") as file:
            file.write("\n".join(meta))
        return file

    @cached_property
    def file_css(self) -> Union[str, None]:
        file = self.__get_file_css()
        if not (file or "").startswith("http"):
            return file
        print("Descargando css de " + file)
        dwn = self.tmp.source + "/" + os.path.basename(file)
        descargar(file, dwn)
        return dwn

    def __get_file_css(self) -> Union[str, None]:
        if self.__arg.css:
            return self.__arg.css
        c = soup.find("link", attrs={'media': "print"})
        if c and "type" in c.attrs and c.attrs["type"] == "text/css":
            css: str = c.attrs.get("href")
            if not isinstance(css, str):
                return None
            if css.startswith("http") or os.path.isfile(css):
                return css
            full_css = str(self.dir_fuente)
            if not css.startswith("/"):
                full_css = full_css + "/"
            css = full_css + css
            return os.path.realpath(css)
        return None

    @cached_property
    def extra_args(self):
        extra_args = list(self._extra_arguments)
        if '--copy-class' in extra_args:
            extra_args.remove('--copy-class')
        if '--toc-depth' not in extra_args:
            extra_args.extend(['--toc-depth', str(self.__arg.toc)])
        if self.file_cover_image and '--epub-cover-image' not in extra_args:
            extra_args.extend(['--epub-cover-image', self.file_cover_image])
        if self.file_metadata and '--epub-metadata' not in extra_args:
            extra_args.extend(['--epub-metadata', self.file_metadata])
        if self.file_css and '--css' not in extra_args:
            extra_args.extend(['--css', self.file_css])
        if self.isHtml and '--parse-raw' not in extra_args:
            extra_args.append('--parse-raw')
        if self.__arg.chapter_level and '--split-level' not in extra_args:
            extra_args.extend(['--split-level', self.__arg.chapter_level])
        return tuple(extra_args)

    @property
    def dc_date(self) -> Union[str, int, None]:
        return self._yml.get('date')

    @property
    def notas(self) -> Union[str, None]:
        return self.__arg.notas

    @property
    def extract(self) -> Union[str, None]:
        return self.__arg.extract

    @property
    def cover_avatar(self) -> Union[str, None]:
        avatar = self._yml.get('cover-avatar')
        if not isinstance(avatar, str):
            return None
        return os.path.abspath(os.path.join(self.dir_fuente, avatar))

    @cached_property
    def notes_format(self) -> Dict[int, str]:
        obj = self._yml.get('notes')
        if not isinstance(obj, dict):
            return {}
        nt_frm: Dict[int, str] = {}
        for k, v in list(obj.items()):
            if len(v) == 0:
                if -1 in nt_frm:
                    raise ValueError(f'notes = {obj}')
                nt_frm[-1] = k
                continue
            for nt in tuple(map(int, v.split(","))):
                if nt in nt_frm:
                    raise ValueError(f'notes = {obj}')
                nt_frm[nt] = k
        return nt_frm

    def parse_note(self, n: str):
        if not self.notes_format:
            return n
        m = re.search(r"\d+", n)
        if not m:
            return n
        num = int(m.group())
        if num in self.notes_format:
            return self.notes_format[num].format(num)
        if -1 in self.notes_format:
            return self.notes_format[-1].format(num)
        return n


M = MetaData(parser.parse_args())

tag_concat = ['u', 'ul', 'ol', 'i', 'em', 'strong']
tag_round = ['u', 'i', 'em', 'span', 'strong', 'a']
tab_block = ['p', 'li', "tr", "thead", "tbody", 'th', 'td', 'div', 'caption', 'h[1-6]', 'figcaption']


def generate_cover(title: str, author: str = None, date_text: str = None, avatar: str = None, output_path="cover.png"):
    if isinstance(date_text, (date, datetime)):
        date_text = date_text.strftime("%Y")
    if isinstance(date_text, int):
        date_text = str(date_text)

    def get_colors():
        if avatar is None:
            return "L", 255, 0
        img: Image.Image = Image.open(avatar)
        if img.mode in ("L", "P", "1"):
            return "L", 255, 0
        return "RGB", (255, 255, 255), (0, 0, 0)

    width, height = 1072, 1448
    mode, bg_color, fg_color = get_colors()

    image = Image.new(mode, (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)

    title_font = ImageFont.truetype("arial.ttf", 90)
    author_font = ImageFont.truetype("arial.ttf", 60)
    date_font = ImageFont.truetype("arial.ttf", 48)

    margin = 80
    draw.rectangle(
        [margin, margin, width - margin, height - margin],
        outline=fg_color,
        width=6
    )

    # Línea decorativa horizontal bajo el título
    line_width = 6
    line_length = width // 3
    line_y_spacing = 60
    extra_shift = 100 if avatar else 0

    # Título (centrado y envuelto)
    wrapped_title = textwrap.fill(title, width=20)
    title_size = draw.multiline_textsize(wrapped_title, font=title_font)
    title_x = (width - title_size[0]) / 2
    title_y = height * 0.22 - extra_shift
    draw.multiline_text((title_x, title_y), wrapped_title, fill=fg_color, font=title_font, align="center")

    # Línea decorativa
    line_x1 = (width - line_length) / 2
    line_x2 = line_x1 + line_length
    line_y = title_y + title_size[1] + line_y_spacing
    draw.line([(line_x1, line_y), (line_x2, line_y)], fill=fg_color, width=line_width)

    # Autor
    author_y = line_y + (line_y_spacing * 0.8)
    if author:
        author_text = f"{author}"
        author_size = draw.textsize(author_text, font=author_font)
        author_x = (width - author_size[0]) / 2
        draw.text((author_x, author_y), author_text, fill=fg_color, font=author_font)
    else:
        author_size = (0, 0)

    # Avatar
    if avatar:
        available_top = author_y + author_size[1] + line_y_spacing
        available_bottom = height * 0.88 - line_y_spacing
        available_height = available_bottom - available_top
        available_width = width - 2 * margin

        avatar_img = Image.open(avatar).convert(mode)
        avatar_w, avatar_h = avatar_img.size
        scale = min(available_width / avatar_w, available_height / avatar_h)
        new_size = (int(avatar_w * scale), int(avatar_h * scale))
        avatar_resized = avatar_img.resize(new_size, Image.LANCZOS)

        avatar_x = int((width - new_size[0]) // 2)
        avatar_y = int(available_top + (available_height - new_size[1]) // 2)
        image.paste(avatar_resized, (avatar_x, avatar_y))

    # Fecha
    if date_text:
        date_size = draw.textsize(date_text, font=date_font)
        date_x = (width - date_size[0]) / 2
        date_y = height * 0.88
        draw.text((date_x, date_y), date_text, fill=fg_color, font=date_font)

    image.save(output_path)
    return output_path


def add_class(n: bs4.Tag, cls: str):
    c = n.attrs.get('class')
    if c is None or isinstance(c, str):
        n.attrs['class'] = ((c or '')+' '+cls).strip()
        return
    if isinstance(c, list):
        c = [x.strip() for x in c if x.strip()]
        n.attrs['class'] = c
    raise ValueError(f"{c} is {type(c)}")


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


def minify_soup(soup: bs4.Tag):
    def __re(rg: str):
        return re.compile(rg, re.MULTILINE | re.DOTALL | re.UNICODE)

    h = str(soup)  # htmlmin.minify(str(soup), remove_empty_space=True)

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
    c = M.tmp.wks + "/" + os.path.basename(s)
    shutil.copy(s, c)
    if len(M.mogrify) > 1:
        call(list(M.mogrify) + [c])
    call(["picopt", "--quiet", "--destroy_metadata",
          "--comics", "--enable_advpng", c])
    despues = os.path.getsize(c)
    if antes > despues:
        shutil.move(c, s)


def str_to_cmd(s: str):
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

print("Convirtiendo con pandoc")
print(f"pandoc '{M.fuente}'", *map(str, M.extra_args), f" -o '{M.out}'")
pypandoc.convert_file(M.fuente,
                      outputfile=M.out,
                      to="epub",
                      extra_args=M.extra_args)

print("Epub inicial de " + sizeof_fmt(os.path.getsize(M.out)))

copy(M.out, M.tmp.root)

print("Descomprimiendo epub")
with zipfile.ZipFile(M.out, 'r') as zip_ref:
    zip_ref.extractall(M.tmp.out)
    zip_ref.close()

print("Eliminando navegación innecesaria")
#os.remove(M.tmp.out + "/EPUB/nav.xhtml")
if M.keep_title:
    with open(M.tmp.out + "/EPUB/text/title_page.xhtml", "r") as f:
        tt_soup = bs4.BeautifulSoup(f, "xml")
    n_body = tt_soup.new_tag("body")
    o_body = tt_soup.find("body")
    for a in o_body.attrs:
        n_body[a] = o_body.attrs[a]
    o_body.name = "div"
    o_body.attrs.clear()
    o_body.attrs["class"] = "title_page"
    o_body.wrap(n_body)
    with open(M.tmp.out + "/EPUB/text/title_page.xhtml", "w") as f:
        f.write(str(tt_soup))
else:
    os.remove(M.tmp.out + "/EPUB/text/title_page.xhtml")

with open(M.tmp.out + "/EPUB/content.opf", "r+") as f:
    d = "".join(ln for ln in f.readlines() if not (M.re_no_content is not None and M.re_no_content.search(ln)) and ln.strip() != "<dc:source></dc:source>")
    if isinstance(M.dc_date, int):
        d = re.sub(r"<dc:date>[^<]+</dc:date>", f"<dc:date>{M.dc_date}</dc:date>", d)
    f.seek(0)
    f.write(d)
    f.truncate()

marcas = {}

with open(M.tmp.out + "/EPUB/toc.ncx", "r+") as f:
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
    content = re.sub(r' xmlns:="', ' xmlns="', str(soup))
    f.seek(0)
    f.write(content)
    f.truncate()

media = M.tmp.out + "/EPUB/media/"
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
    with open(M.tmp.out + "/EPUB/content.opf", "r+") as f:
        d = [l for l in f.readlines() if not re_imgdup.search(l)]
        f.seek(0)
        f.write("".join(d))
        f.truncate()
    print("Eliminadas imágenes duplicadas")

xhtml = sorted(glob.glob(M.tmp.out + "/EPUB/text/ch*.xhtml"))
notas = []
xnota = None
count = 1

if M.notas:
    for html in xhtml:
        with open(html, "r+") as f:
            soup = bs4.BeautifulSoup(f, "xml")
            if soup.find("h1", text=M.notas):
                xnota = os.path.basename(html)
                break

if xnota is None:
    xnota = os.path.basename(xhtml[-1])            


if os.path.isfile(M.tmp.out + "/EPUB/nav.xhtml"):
    with open(M.tmp.out + "/EPUB/nav.xhtml", "r+") as f:
        soup = bs4.BeautifulSoup(f, "xml")
        for a in soup.select("a"):
            href: str = a.attrs.get("href")
            if href == "text/title_page.xhtml" and not M.keep_title:
                a.find_parent("li").extract()
                continue
            if a and "#" in href:
                href, antes = href.rsplit("#", 1)
                despues = simplifica(antes)
                if despues and antes != despues:
                    a.attrs["href"] = href + "#" + despues
        minified = minify_soup(soup)
        minified = re.sub(r' xmlns:="', ' xmlns="', minified)
        f.seek(0)
        f.write(minified)
        f.truncate()

fixNotas = {}
for html in xhtml:
    chml = os.path.basename(html)
    with open(html, "r+") as f:
        soup = bs4.BeautifulSoup(f, "xml")
        if M.extract:
            for n in soup.select(M.extract):
                n.extract()
        for c in soup.select("div"):
            if "id" in c.attrs and c.attrs["id"] in marcas:
                c.attrs["id"] = marcas[c.attrs["id"]]
        for ids in soup.select("*[id]"):
            antes = ids.attrs["id"]
            despues = simplifica(antes)
            if despues and antes != despues:
                ids.attrs["id"] = despues
        for p in soup.select("table p") + soup.select("figure p"):
            p.unwrap()
        for i in soup.select("img"):
            if "src" in i.attrs and i.attrs["src"] in imgdup:
                i.attrs["src"] = imgdup[i.attrs["src"]]
        if chml == xnota:
            div = soup.select_one("section")
            for n in notas:
                div.append(n)
            for _id, xml in fixNotas.items():
                a = div.find("a", attrs={"href": "#"+_id})
                if a:
                    a.attrs["href"] = xml + a.attrs["href"]
        else:
            footnotes = soup.select_one("section.footnotes")
            if footnotes:
                bak_count = count
                for p in footnotes.select("p"):
                    a = p.select_one("a.footnote-back")
                    if a['href'].startswith("#"):
                        a['href'] = chml + a['href']
                    p['id'] = "fn" + str(count)
                    a['class'] = "volver"
                    a.string = "<<"
                    p.append(a)
                    a.insert_before(" ")
                    first_text = p.find(text=True)
                    first_text.replace_with(re.sub(r"^[\s\.]+", "", first_text.string))
                    sup = soup.new_tag("sup")
                    sup.string = M.parse_note("[" + str(count) + "]")
                    p.insert(0, sup)
                    p.insert(1, " ")
                    notas.append(p)
                    count = count + 1
                footnotes.extract()
                count = bak_count
                for a in soup.select("a.footnote-ref"):
                    a['href'] = xnota + "#fn" + str(count)
                    sup = a.find("sup")
                    if not sup:
                        sup = soup.new_tag("sup")
                        a.string = ""
                        a.append(sup)
                    sup.string = M.parse_note("[" + str(count) + "]")
                    if a.previous_sibling is None:
                        raise Exception(str(a)+" previous_sibling = None")
                    if len(a.previous_sibling.string) > 0 and len(a.previous_sibling.strip()) == 0:
                        a.previous_sibling.extract()
                    count = count + 1
            else:
                for a in soup.select("a.footnote-ref"):
                    if a['href'].startswith("#"):
                        a['href'] = xnota + a['href']
                        fixNotas[a['id']] = chml

        for c in M.get_class_copy_nodes():
            fnd = soup.find(lambda t: t.name == c.name and re_sp.sub(
                " ", t.get_text()).strip() == re_sp.sub(" ", c.get_text()).strip())
            if fnd and "class" not in fnd.attrs:
                fnd.attrs["class"] = c.attrs["class"]

        for img in soup.findAll("img"):
            if "alt" not in img.attrs:
                img.attrs["alt"]=""

        for n in soup.select("article"):
            n.name = "div"

        if M.isMd:
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
                last_tr_th = None
                first_tr_td = None
                tr_to_th = []
                for i, tr in enumerate(trs):
                    if any(map(get_text, tr.select("td"))):
                        if first_tr_td is None:
                            first_tr_td = i
                        continue
                    last_tr_th = i
                    for td in tr.select("td"):
                        td.name = "th"
                    tr_to_th.append(tr)
                if None not in (first_tr_td, last_tr_th) and last_tr_th < first_tr_td:
                    table = tbody.find_parent("table")
                    for tr in tr_to_th:
                        thead = table.select_one("thead")
                        if thead is None:
                            thead = soup.new_tag('thead')
                            table.insert(0, thead)
                        thead.append(tr)
            for tbody in soup.select("thead, tbody"):
                for i, tr in enumerate(tbody.select("tr")):
                    tr.attrs["class"] = "odd" if (i % 2) == 0 else "even"
            for c in soup.select("cite"):
                p = c.parent
                q = p.parent
                if q.name == "blockquote" and p.name == "p" and re_sp.sub(" ", p.get_text()).strip() == re_sp.sub(" ", c.get_text()).strip():
                    p.attrs["class"] = "cite"
                    q.attrs["class"] = "cite"

        for img in soup.select("a > img"):
            a = img.find_parent("a")
            if get_text(a) is not None:
                continue
            chls = a.select(":scope *")
            if len(chls) == 1 and chls[0] == img:
                add_class(a, "pandoc_a_img")
        minified = minify_soup(soup)
        minified = re.sub(r' xmlns:="', ' xmlns="', minified)
        f.seek(0)
        f.write(minified)
        f.truncate()

if len(M.mogrify)>1 and len(imgs) > 0:
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

if M.execute:
    call([M.execute, M.tmp.out, M.fuente])

with zipfile.ZipFile(M.out, "w") as zip_file:
    zip_file.write(M.tmp.out + '/mimetype', 'mimetype',
                   compress_type=zipfile.ZIP_STORED)
    z = len(M.tmp.out) + 1
    for root, dirs, files in os.walk(M.tmp.out):
        for f in files:
            path = os.path.join(root, f)
            name = path[z:]
            if name != 'mimetype':
                zip_file.write(path, name, compress_type=zipfile.ZIP_DEFLATED)

if M.ebook_meta:
    check_output(["ebook-meta"] + list(M.ebook_meta) + [M.out])

print("Epub final de " + sizeof_fmt(os.path.getsize(M.out)))

call(["epubcheck", M.out])
