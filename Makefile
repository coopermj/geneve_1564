BOOK_NAME=geneve_1564
TEXINPUTS=microtype:
FONTSDIR=fonts
TODAY=$(shell date --iso)
TARGETS=$(BOOK_NAME)
LATEX_INTERACTION=batchmode

all: pdf

pdf: $(addsuffix .pdf,$(TARGETS))

%.pdf: %.tex $(MONTHS)
	OSFONTDIR=$(FONTSDIR) TEXINPUTS=$(TEXINPUTS) lualatex -shell-escape -interaction=$(LATEX_INTERACTION) $<
	OSFONTDIR=$(FONTSDIR) TEXINPUTS=$(TEXINPUTS) lualatex -shell-escape -interaction=$(LATEX_INTERACTION) $<

net_bible.pdf: net_bible.tex livres/old_testament.tex livres/new_testament.tex
	OSFONTDIR=$(FONTSDIR) TEXINPUTS=$(TEXINPUTS) lualatex -shell-escape -interaction=$(LATEX_INTERACTION) $<
	OSFONTDIR=$(FONTSDIR) TEXINPUTS=$(TEXINPUTS) lualatex -shell-escape -interaction=$(LATEX_INTERACTION) $<

generate:
	python3 scripts/generate_bible.py --output-dir livres

esv_bible.pdf: esv_bible.tex
	OSFONTDIR=$(FONTSDIR) TEXINPUTS=$(TEXINPUTS) lualatex -shell-escape -interaction=$(LATEX_INTERACTION) $<
	OSFONTDIR=$(FONTSDIR) TEXINPUTS=$(TEXINPUTS) lualatex -shell-escape -interaction=$(LATEX_INTERACTION) $<

generate-esv:
	python3 scripts/generate_esv.py --output-dir livres_esv

fetch-annotations:
	python3 scripts/annotation_fetcher.py

build-annotated:
	python3 scripts/build_annotated.py

build-annotated-book:
	python3 scripts/build_annotated.py --books $(BOOK)

clean:
	rm -f *.pdf *.ps *.aux *.log *.out *.lol
	rm -f *.idx *.ind *.ilg *.toc *.dvi

