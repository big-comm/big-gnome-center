# BigStyle GTK 4 module (vendored)

Copied unchanged from BigStyle (`packages/gtk4-module`, `Makefile` and `src/`):

- Repository: https://github.com/biglinux/bigstyle
- Branch: `dev-bigbruno`
- Commit: `ee8ae2b6dbdde2eb16d773f0c064e1c4327f3eb8`
  ("gtk4-module: drop a window's own backdrop-filter where it asks the blur")
- Author: Bruno Gonçalves
- License: GPL-3.0-or-later

Why it is here: GTK's `backdrop-filter` redraws the window backdrop on every
frame. The module asks Mutter for the same blur and drops that redraw (see
`docs/FROSTED_GLASS.md`). The `bigstyle` package is not yet installable in
BigCommunity, as its `big-qt-theme` dependencies are unpublished.

Install path is the same as BigStyle's, and the package conflicts with
`bigstyle`: two copies would each create a background-effect object for the
same surface, a Wayland protocol error that ends the program.

Remove this directory and depend on `bigstyle` once that package is published.
Do not edit the sources here; change them upstream and copy them again.
