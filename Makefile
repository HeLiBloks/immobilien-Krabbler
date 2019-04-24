SHELL:=/bin/bash
EXECUTABLES_doxygen = doxygen doxypy

ListSitePackages:
	SITEPACKAGES:=$(shell python -c 'import site; site.getsitepackages()')
	$(shell echo $$SITEPACKAGES)

pyreverse_uml:
	ifeq (, $(shell which pyreverse))
		$(error "No pyreverse in $(PATH), consider pip installing pyreverse")
	endif
	pyreverse -o pdf -p '/tmp/uml_pyreverse.pdf' && zathura /tmp/uml_pyreverse.pdf

tags2uml:
	find . -type f -iname '*.py' -not -path "./venv/*" -print | \
	ctags -f /tmp/tags --fields=+latinK -L -
	tags2uml --members 1 --methods 1 --infile /tmp/tags --outfile - | \
	dot -Tpdf |zathura -

doxygen:
	test -d ./doc || mkdir doc
	doxygen -g Doxygen
	sed -i -re '/^EXTRACT_(ALL)|(PRIVATE)|(STATIC)/ s/NO/YES/g; /^CALL_GRAPH/ s/NO/YES/; /^HAVE_DOT/ s/NO/YES/g; ' \
	-e '/^FILE_PATTERNS/     s/=(.*)/& *.txt *.py / ' \
	-e '/^FILTER_SOURCE_FILES/   s/=.*/= YES/  ' \
	-e '/^INPUT_FILTER/          s/=(.*)/& \/usr\/bin\/doxypy /' \
	-e "/PROJECT_NAME/          s/=.*/= $(shell basename $$PWD )/" \
	-e '/^OUTPUT_DIRECTORY/  s/=(.*)/& doc/' \
	-e '/^RECURSIVE/ s/NO/YES/' \
	-e '/^OPTIMIZE_OUTPUT_FOR_JAVA/ s/=.*/= YES/' \
	-e '/^GENERATE_TAGFILE/ s/=.*/= YES/' Doxygen
	# run doxygen with created file
	test $$? -eq 0 && doxygen Doxygen

initVirtualEnvInPWD:
	virtualenv -p /usr/bin/python ./env && \
	source env/bin/activate ; pip3 install selenium==3.4.1 SQLAlchemy==1.2.11 SQLAlchemy-Utils==0.32.14
	$(shell egrep '^env' .gitignore || echo "env" >> .gitignore )
	# find .  -iname '*.py' -exec  grep -Po '^\s*(from\s\K\w+)?(?=\s*import\s)' {} \; | sort -u ;

un_initVirtualEnvInPWD:
	

# see https://www.fusionbox.com/blog/detail/navigating-your-django-project-with-vim-and-ctags/590/
ctagsSysTags:
	ctags -R --fields=+l --languages=python --python-kinds=-iv -f ./tags $$(python -c "import os, sys; print(' '.join('{}'.format(d) for d in sys.path if os.path.isdir(d)))")

ctags:
	find -type f -iname '*.py' -print | \
	ctags --fields=+l --languages=python --python-kinds=-iv -f ./tags -L -

pyCscope:
	pycscope .

clean:
	rm -rf ghostdriver.log tags ./doc Doxygen

create_report_view:
	test -f immobilien.db && sqlite3 ./immobilien.db "CREATE VIEW _immos AS SELECT datetime(unixtimestamp,'unixepoch','localtime') AS Datum, printf('%.2f', immobilien.kaufpreis) AS Kaufpreis, printf('%.2f', immobilien.kaltmiete) AS Kaltmiete, printf('%.2f',kaufpreis/wohnfläche) AS 'K_Eur/M²', printf('%.2f',kaltmiete/wohnfläche) AS 'M_Eur/M²', printf('%.2f',wohnfläche) AS Wohnfläche, printf('%.2f',grundstück) AS 'Grundstück', address, district FROM immobilien ORDER BY Datum DESC"
