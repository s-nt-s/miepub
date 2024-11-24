import bs4
import re

tag_concat = ('u', 'ul', 'ol', 'i', 'em', 'strong')
tag_round = ('u', 'i', 'em', 'span', 'strong', 'a')
tag_trim = ('li', 'th', 'td', 'div', 'caption', 'h[1-6]', 'figcaption')
tag_right = ('p', )


def minify_soup(soup: bs4.Tag):
    def __re(rg: str):
        return re.compile(rg, re.MULTILINE | re.DOTALL | re.UNICODE)
    h = str(soup) # htmlmin.minify(str(soup), remove_empty_space=True)
    for t in tag_concat:
        r = __re(r"</" + t + r">(\s*)<" + t + r">")
        h = r.sub(r"\1", h)
    for t in tag_round:
        r = __re("(<" + t + r">)(\s+)")
        h = r.sub(r"\2\1", h)
        r = __re(r"(<" + t + r" [^>]+>)(\s+)")
        h = r.sub(r"\2\1", h)
        r = __re(r"(\s+)(</" + t + r">)")
        h = r.sub(r"\2\1", h)
    for t in tag_trim:
        r = __re(r"(<" + t + r">)\s+")
        h = r.sub(r"\1", h)
        r = __re(r"\s+(</" + t + r">)")
        h = r.sub(r"\1", h)
    for t in tag_right:
        r = __re(r"\s+(</" + t + r">)")
        h = r.sub(r"\1", h)
        r = __re(r"(<" + t + ">) +")
        h = r.sub(r"\1", h)
    return h
