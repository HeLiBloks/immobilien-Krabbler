SHELL:=/bin/bash

SITEPACKAGES:=$(shell python -c 'import site; site.getsitepackages()')

ListSitePackages:
	$(shell echo $$SITEPACKAGES)
	# python -c 'import site; site.getsitepackages()'

uml:
	pyreverse -o pdf -p '/tmp/uml_pyreverse.pdf' && zathura /tmp/uml_pyreverse.pdf

tags2uml:
	find . -type f -iname '*.py' -not -path "./venv/*" -print | \
	ctags -f /tmp/tags --fields=+latinK -L -
	tags2uml --members 1 --methods 1 --infile /tmp/tags --outfile - | \
	dot -Tpdf |zathura -

doxygen:
	[[ ! -f ./doc ]] && mkdir doc
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
	doxygen Doxygen

initVirtualEnvInPWD:
	{ find .  -iname '*.py' -exec  grep -Po '^\s*(from\s\K\w+)?(?=\s*import\s)' {} \; | sort -u ;
	virtualenv -p /usr/bin/python ./env
	echo "./env" >> .gitignore

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


