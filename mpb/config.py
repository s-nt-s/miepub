from dataclasses import dataclass
from os.path import realpath, isfile
from functools import cached_property
from os import access, X_OK
import re

re_sp = re.compile(r"\s+")

@dataclass(frozen=True)
class Config:
    out: str
    toc: int
    cover: str
    metadata: str
    css: str
    chapter_level: int
    txt_cover: str
    gray: bool
    trim: bool
    copy_class: bool
    width: int
    notas: str
    execute: str
    keep_title: bool
    fuente: str

    def __post_init__(self):
        if not isfile(self.fuente):
            raise ValueError(f"{self.fuente} no existe")
        if self.execute and (not isfile(self.execute) or not access(self.execute, X_OK)):
            raise ValueError(f"{self.execute} no es un programa ejecutable")
        name, ext = self.fuente.rsplit(".", 1)
        ext = ext.lower()
        if ext not in ("html", "md"):
            raise ValueError("fuente debe ser .html o .md")
        if self.out is None:
            object.__setattr__(self, 'out', name+".epub")
        for k in ('out', 'fuente', 'execute'):
            object.__setattr__(self, k, realpath(object.__getattribute__(k)))

    @cached_property
    def source_extension(self):
        return self.fuente.rsplit(".", 1)[-1].lower()

    @property
    def isMD(self):
        return self.source_extension == "md"

    @property
    def isHTML(self):
        return self.source_extension == "html"

    @property
    def prefix(self):
        name, ext = self.fuente.rsplit(".", 1)
        return re_sp.sub("_", name.strip()) + "_"

    @property
    def no_content(self):
        if self.keep_title:
            return re.compile(r'<item id="nav" |<itemref idref="nav" |href="nav.xhtml')
        return re.compile(r'<item id="nav" |<item id="title_page" |<item id="title_page_xhtml" |<itemref idref="title_page" |<itemref idref="title_page_xhtml" |<itemref idref="nav" |href="nav.xhtml')

    @cached_property
    def mogrify(self):
        mogrify = ["mogrify"]
        if self.trim:
            mogrify.extend(["-strip", "+repage", "-fuzz", "600", "-trim"])
        if self.gray:
            mogrify.extend(["-colorspace", "GRAY"])
        if self.width:
            mogrify.extend(["-resize", str(self.width) + ">"])
        if len(mogrify):
            return tuple()
        return tuple(mogrify)

    def pandoc_extra_args(self):
        extra_args = []
        if '--toc-depth' not in extra_args:
            extra_args.extend(['--toc-depth', str(self.toc)])
        if self.cover and '--epub-cover-image' not in extra_args:
            extra_args.extend(['--epub-cover-image', self.cover])
        if self.metadata and '--epub-metadata' not in extra_args:
            extra_args.extend(['--epub-metadata', self.metadata])
        if self.css and '--epub-stylesheet' not in extra_args:
            extra_args.extend(['--epub-stylesheet', self.css])
        if self.isHTML and '--parse-raw' not in extra_args:
            extra_args.append('--parse-raw')
        if self.chapter_level and '--epub-chapter-level' not in extra_args:
            extra_args.extend(['--epub-chapter-level', self.chapter_level])
        return tuple(extra_args)