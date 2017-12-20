import os.path
import zipfile
import bs4
import tempfile
import os
import glob

xhtml=sorted(glob.glob('ch*.xhtml'))
fnotas=xhtml[-1]
xnotas = open(fnotas,"r+")
snotas = bs4.BeautifulSoup(xnotas)
dnotas = snotas.select("body > div")[0]

del xhtml[-1]

count=1

for fichero in xhtml:
	htmlDoc = open(fichero,"r+")
	soup = bs4.BeautifulSoup(htmlDoc)

	notas=soup.select("div.footnotes")
	if len(notas)>0:
		for p in soup.select("div.footnotes li p"):
			a=p.select("a")[-1]
			if a['href'].startswith("#"):
				a['href']=fichero+a['href']
			dnotas.append(p)
		soup.select("div.footnotes")[0].extract()
		refs=soup.select("a.footnoteRef")
		for a in refs:
			a['href']=fnotas+"#fn"+str(count)
			a.select("sup")[0].string="["+str(count)+"]"
			if len(a.previous_sibling.string)>0 and len(a.previous_sibling.strip())==0:
				a.previous_sibling.extract()
			count=count+1
		htmlDoc.close()
		html = str(soup) # soup.prettify("utf-8",formatter="minimal")
		with open(fichero, "wb") as file:
			file.write(html)
	else:
		htmlDoc.close()

count=1
dnotas = snotas.select("body > div > p")
for n in dnotas:
	n['id']="fn"+str(count)
	sup = soup.new_tag("sup")
	sup.string="["+str(count)+"]"
	n.insert(0,sup)
	n.insert(1," ")
	a=n.select("a")[-1]
	a['class']="volver"
	a.insert_before(" ")
	a.string="<<"

	count=count+1

xnotas.close()
html = str(snotas) #snotas.prettify("utf-8",formatter="minimal")
with open(fnotas, "wb") as file:
	file.write(html)
