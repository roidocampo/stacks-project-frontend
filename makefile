
all: vendor-update chapters staticfiles

vendor-setup: lib/stacks-project

lib/stacks-project:
	cd lib && git clone https://github.com/stacks/stacks-project.git

vendor-update: vendor-setup
	cd lib/stacks-project && git pull

chapters: | web
	python lib/proc_stacks_chapter.py

staticfiles: web/mathjax_conf.js web/style.css

web/mathjax_conf.js: static/mathjax_conf.js | web
	cp static/mathjax_conf.js web/

web/style.css: static/style.css | web
	cp static/style.css web/

web:
	mkdir web

clean:
	rm -rf lib/stacks-project
	rm -rf web
