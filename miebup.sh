#!/bin/bash

SCP=$(dirname $(realpath "$0"))
DIR=$(pwd)
MD=`ls *.md | head -n 1`
if [ -z "$MD" ]; then
	echo "Markdown no encontrado"
	exit 1
fi
echo "Convirtiendo $MD"

EPUB=`echo $MD | sed 's/md$/epub/'`

TMP=$(mktemp -d)

cp "$MD" "$TMP"

TMD="$TMP/$MD"
sed -r 's/^([\t ]*)[ivxdlcm]+\. /\1#. /i' -i "$TMD"
sed -r 's/^([\t ]*[A-Z])\. /\1) /i' -i "$TMD"
sed -r 's/^([1-9]+[0-9]*)\) /\1\\) /' -i "$TMD"

NT=0
if grep --quiet "\[\^1\]" "$TMD"; then
	NT=1
	if ! grep --quiet "^# Notas" "$TMD"; then
		echo "" >> "$TMD"
		echo "# Notas" >> "$TMD"
		echo "" >> "$TMD"
	fi
fi

if [ -f "~/.pandoc/epub.css" ]; then
	cp ~/.pandoc/epub.css ~/.pandoc/epub.css.bak
fi

if [ -f "$DIR/epub.css" ]; then
	cp "$DIR/epub.css" ~/.pandoc/
elif [ -f "$SCP/epub.css" ]; then
	cp "$SCP/epub.css" ~/.pandoc/
fi

echo "Ejecutando pandoc"
pandoc -S --from markdown+ascii_identifiers -o "$TMP/$EPUB" "$TMD"

if [ -f "~/.pandoc/epub.css.bak" ]; then
	cp ~/.pandoc/epub.css.bak ~/.pandoc/epub.css
	rm ~/.pandoc/epub.css.bak
fi

cd "$TMP"

rm "$MD"

unzip -q "$EPUB"

rm "$EPUB"

rm nav.xhtml
rm title_page.xhtml

sed '/<item id="nav" /d' -i content.opf
sed '/<item id="title_page" /d' -i content.opf
sed '/<itemref idref="title_page" /d' -i content.opf
sed '/<itemref idref="nav" /d' -i content.opf
sed '/href="nav.xhtml"/d' -i content.opf
perl -0777 -pe 's/\s*<navPoint id=.navPoint-0.>\s*<navLabel>\s*<text>.*?\s*<\/navLabel>\s*<content src="title_page.xhtml" \/>\s*<\/navPoint>//igs' -i toc.ncx

if [ $NT -eq 1 ]; then
	echo "Generando notas"
	python "$SCP/notas.py"
fi

zip -r -q "$EPUB" *
cp "$EPUB" "$DIR/$EPUB"
