Script sencillo para generar epub sorteando algunos bugs de [pandoc](https://github.com/jgm/pandoc/) y dejandolo a mi gusto.

Uso: `miepub.sh fichero_fuente`

Si el argumento `fichero_fuente` no es pasado pero en el directorio actual existe un unico fichero `.md`, tomará este como fichero fuente.

Nota: `epub.css` esta pensado para Kobo Mini.

Para optimizar las imagenes requiere:

* `picopt` https://github.com/ajslater/picopt
* `ImageMagick` https://www.imagemagick.org/script/index.php
* `exiftool` http://www.sno.phy.queensu.ca/~phil/exiftool/
