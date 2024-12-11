SUBDIRS := $(wildcard */.)
SUBDIRS := $(filter-out archive/. autosave/.,$(SUBDIRS))

all: install

install: $(SUBDIRS)
$(SUBDIRS):
	$(MAKE) -C $@

.PHONY: all $(SUBDIRS)
