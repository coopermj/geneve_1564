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

generate:
	python3 scripts/generate_bible.py --output-dir livres

esv_bible.pdf: esv_bible.tex
	OSFONTDIR=$(FONTSDIR) TEXINPUTS=$(TEXINPUTS) lualatex -shell-escape -interaction=$(LATEX_INTERACTION) $<
	OSFONTDIR=$(FONTSDIR) TEXINPUTS=$(TEXINPUTS) lualatex -shell-escape -interaction=$(LATEX_INTERACTION) $<

generate-esv:
	python3 scripts/generate_esv.py --output-dir livres_esv

clean:
	rm -f *.pdf *.ps *.aux *.log *.out *.lol
	rm -f *.idx *.ind *.ilg *.toc *.dvi

# ---- Consolidated edition build targets ----
LL = OSFONTDIR=fonts TEXINPUTS=microtype: lualatex -shell-escape -interaction=nonstopmode
GEN = python3 scripts/generate.py --edition

define build_edition
	$(GEN) $(2)
	$(LL) $(1).tex
	$(LL) $(1).tex
endef

.PHONY: esv net-reading net-notes geneva geneve-1564 all-editions
esv:
	$(call build_edition,esv_bible,esv)
net-reading:
	$(call build_edition,net_reading,net)
net-notes:
	$(call build_edition,net_notes,net)
geneva:
	$(call build_edition,geneva_bible,geneva)
geneve-1564:
	$(LL) geneve_1564.tex
	$(LL) geneve_1564.tex
all-editions: esv net-reading net-notes geneva geneve-1564

