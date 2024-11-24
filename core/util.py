import unicodedata


def sizeof_fmt(num: float, suffix: str = 'B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Y', suffix)


def simplifica(s: str):
    s = unicodedata.normalize('NFKD', s)
    b = s.encode('ascii', 'ignore')
    s = b.decode('ascii', 'ignore')
    s = s.strip(". ")
    s = s.strip()
    return s
