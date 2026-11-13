# A Makefile rather than a build system: three translation units plus the
# protocol glue. `background-effect.c` and `window-frame.c` are shared with
# the GTK 3 module.
#
# The glue is generated here rather than committed. `wayland-scanner` reads the
# XML that `wayland-protocols` installs, so the code always matches the protocol
# version on the machine that built it, and there is no generated file in the
# tree to go stale against it.

PREFIX ?= /usr
LIBDIR ?= $(PREFIX)/lib
DESTDIR ?=

PROTOCOL_DIR := $(shell pkg-config --variable=pkgdatadir wayland-protocols)
PROTOCOL_XML := $(PROTOCOL_DIR)/staging/ext-background-effect/ext-background-effect-v1.xml
SCANNER := $(shell pkg-config --variable=wayland_scanner wayland-scanner)

BUILD := build
LIBRARY := $(BUILD)/libbigstyle-gtk4.so
GENERATED := $(BUILD)/ext-background-effect-v1-client-protocol.h \
             $(BUILD)/ext-background-effect-v1-protocol.c

CFLAGS ?= -O2 -g
override CFLAGS += -std=c11 -Wall -Wextra -Wno-unused-parameter -fPIC -fvisibility=hidden
override CFLAGS += $(shell pkg-config --cflags gtk4 wayland-client) -I$(BUILD)
LDLIBS := $(shell pkg-config --libs gtk4 wayland-client)
override LDFLAGS += -Wl,-z,nodelete

all: $(LIBRARY)

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/ext-background-effect-v1-client-protocol.h: | $(BUILD)
	$(SCANNER) client-header $(PROTOCOL_XML) $@

$(BUILD)/ext-background-effect-v1-protocol.c: | $(BUILD)
	$(SCANNER) private-code $(PROTOCOL_XML) $@

$(LIBRARY): src/bigstyle-gtk4.c src/background-effect.c src/background-effect.h \
             src/window-frame.c src/window-frame.h $(GENERATED)
	$(CC) $(CFLAGS) -shared -o $@ src/bigstyle-gtk4.c src/background-effect.c src/window-frame.c \
	    $(BUILD)/ext-background-effect-v1-protocol.c $(LDFLAGS) $(LDLIBS)

install: $(LIBRARY)
	install -Dm755 $(LIBRARY) $(DESTDIR)$(LIBDIR)/gtk-4.0/4.0.0/immodules/libbigstyle-gtk4.so

clean:
	rm -rf $(BUILD)

.PHONY: all install clean
