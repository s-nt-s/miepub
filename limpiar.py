#!/usr/bin/python3

import re
import bs4
from urllib.parse import urlparse
from os.path import splitext

tag_concat = ['u', 'ul', 'ol', 'i', 'em', 'strong', 'b']
tag_round = ['u', 'i', 'em', 'span', 'strong', 'a', 'b']
tag_trim = ['li', 'th', 'td', 'div', 'caption', 'h[1-6]', 'p']

sp = re.compile("\s+")
re_scribd = re.compile(r"^(https://www.scribd.com/embeds/\d+)/.*")
re_youtube = re.compile(r"https://www.youtube.com/embed/(.+?)\?.*")

heads = ["h1", "h2", "h3", "h4", "h5", "h6"]
block = heads + ["p", "div", "table", "article"]
inline = ["span", "strong", "b", "del", "i", "em"]

attrs_imp = ["src", "href", "id", "class", "colspan", "rowspan", "alt" ]

urls = ["#", "javascript:void(0)"]

def load(html):
    if isinstance(html, bs4.Tag):
        return html, str(html), None
    html = html.strip()
    origen = None
    soup = None
    if html.startswith("<"):
        soup = bs4.BeautifulSoup(f.read(), 'lxml')
    else:
        origen = html
        with open(source) as f:
            soup = bs4.BeautifulSoup(f.read(), 'lxml')
    return soup, str(soup), origen

def vacio(n):
    txt = sp.sub("", n.get_text().strip())
    return len(txt)==0

def version_de(src1, src2):
    if src1 == src2:
        return False
    if "." not in src1 or "." not in src2:
        return False
    rut1, ext1 = src1.rsplit('.', 1)
    rut2, ext2 = src2.rsplit('.', 1)
    return ext1 == ext2 and rut1.startswith(rut2)
    
    

class Limpiar:

    def __init__(self, html, noscript=False, iframe_to_anchor=False, resolve_images=False, clear_attr=None):
        self.load(html)
        self.noscript = noscript
        self.iframe_to_anchor = iframe_to_anchor
        self.resolve_images = resolve_images
        self.clear_attr = (clear_attr or [])

    def load(self, html):
        self.soup, self.html, self.origen = load(html)

    def limpiar(self):
        self.limpiar_soup()
        self.limpiar_html()

    def limpiar_soup(self):
        for n in self.soup.findAll(text=lambda text: isinstance(text, bs4.Comment)):
            n.extract()
        if self.noscript:
            for n in self.soup.findAll("script"):
                n.extract()
            for n in self.soup.findAll("noscript"):
                n.unwrap()
        if self.iframe_to_anchor:
            for i in self.soup.findAll("iframe"):
                src = i.attrs["src"]
                busca_href = src
                is_scribd = re_scribd.match(src)
                is_youtube = re_youtube.match(src)
                if is_scribd:
                    busca_href = is_scribd.group(1)
                    busca_href = busca_href.replace("/embeds/","/(doc|embeds)/")
                    busca_href = re.compile("^"+busca_href+"(/.*)?$")
                    src = src.replace("/embeds/","/doc/")
                elif is_youtube:
                    busca_href = is_youtube.group(1)
                    src = "https://www.youtube.com/watch?v=" + busca_href
                    busca_href = re.compile("^https?://www.youtube.com/.*\b"+busca_href+"\b.*$")
                if self.soup.findAll("a", attrs={'href': busca_href}):
                    i.extract()
                else:
                    i.name="a"
                    i.attrs.clear()
                    i.attrs["href"] = src
                    i.attrs["target"] = "_blank"
                    i.string=src
        if self.resolve_images:
            for img in self.soup.select("a > img"):
                a = img.parent
                if vacio(a) and a.name == "a":
                    href = a.attrs["href"]
                    src = img.attrs["src"]
                    _, ext1 = splitext(urlparse(href).path)
                    _, ext2 = splitext(urlparse(src).path)
                    if ext1 == ext2:
                        img.attrs["src"] = href
                        a.unwrap()
                    else:
                        srcset = img.attrs.get("srcset", "").split(", ")[-1].split(" ")[0].strip()
                        if len(srcset)>0:
                            img.attrs["src"] = srcset
            for f in self.soup.findAll(["figure", "p", "li"]):
                imgs = f.findAll("img")
                if len(imgs)>1:
                    srcs = set([i.attrs["src"] for i in imgs])
                    for src in srcs:
                        visto = []
                        for i in f.findAll("img"):
                            s = i.attrs["src"]
                            if s in visto or version_de(s, src):
                                i.extract()
                            visto.append(s)
                        
        for i in self.soup.findAll(block):
            if vacio(i) and not i.find("img") and not i.find("iframe"):
                i.extract()
        for i in self.soup.findAll(heads):
            if vacio(i):
                i.name="p"
        for i in self.soup.findAll(inline):
            if vacio(i):
                i.unwrap()
        for i in self.soup.findAll(block + inline):
            i2 = i.select(" > " + i.name)
            if len(i2) == 1:
                txt = sp.sub("", i.get_text()).strip()
                txt2 = sp.sub("", i2[0].get_text()).strip()
                if txt == txt2:
                    i.unwrap()
        for n in self.clear_attr:
            for i in self.soup.findAll(n):
                attrs = {a : i.attrs[a] for a in attrs_imp if a in i.attrs}
                i.attrs.clear()
                i.attrs = attrs
        for n in self.soup.findAll():
            for a in n.attrs:
                v = n.attrs[a]
                if isinstance(v, str):
                    n.attrs[a] = v.strip()
                elif isinstance(v, list):
                    n.attrs[a] = [i.strip() for i in v]
        self.check_heads()
        self.html = str(self.soup)

    def check_heads(self, inicio=0, nodo=None):
        if not nodo:
            nodo = self.soup
        hs=[]
        for i in range(1,7):
            h = nodo.findAll("h"+str(i))
            if len(h):
                hs.append(h)
        i = inicio + 1
        for _h in hs:
            for h in _h:
                h.name = "h"+str(i)
            i = i + 1
        '''
        for i in range(6, inicio + 1,-1):
            h1 = nodo.findAll("h"+str(i))
            h0 = nodo.findAll("h"+str(i-1))
            if len(h1)>0 and len(h0)==0:
                for h in h1:
                    h.name = "h" + str(i-1)
        hs = nodo.findAll(["h"+str(i) for i in range(inicio+1, 7)])
        i = 0
        for h in hs:
            n = int(h.name[1])
            if i != 0 and n>i+1:
                h.name = "h" + str(i+1)
        '''
        return nodo

    def limpiar_html(self):
        self.html = self.html.replace('‎', '').strip()
        r = re.compile(r"(\s*\.\s*)</a>", re.MULTILINE | re.DOTALL)
        self.html = r.sub(r"</a>\1", self.html)
        for t in tag_concat:
            r = re.compile(
                r"</" + t + r">(\s*)<" + t + r">", re.MULTILINE | re.DOTALL)
            self.html = r.sub(r"\1", self.html)
        for t in tag_round:
            r = re.compile(
                r"(<" + t + r">|<" + t + r" [^>]+>)(\s+)", re.MULTILINE | re.DOTALL)
            self.html = r.sub(r"\2\1", self.html)
            r = re.compile(
                r"(\s+)(</" + t + r">)", re.MULTILINE | re.DOTALL)
            self.html = r.sub(r"\2\1", self.html)
            r = re.compile(
                r"(<br/?>)(</" + t + r">)", re.MULTILINE | re.DOTALL)
            self.html = r.sub(r"\2\1", self.html)
        for t in tag_trim:
            r = re.compile(
                r"(<" + t + r">)\s+", re.MULTILINE | re.DOTALL)
            self.html = r.sub(r"\1", self.html)
            r = re.compile(
                r"\s+(</" + t + r">)", re.MULTILINE | re.DOTALL)
            self.html = r.sub(r"\1", self.html)

        self.soup = bs4.BeautifulSoup(self.html, 'lxml')
        
