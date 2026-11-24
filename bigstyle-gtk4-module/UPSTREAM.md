# BigStyle GTK 4 module (vendored)

Copied from BigStyle (`packages/gtk4-module`, `Makefile` and `src/`), with one
local change listed below:

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

## Local change

`src/bigstyle-gtk4.c`: `backdrop_shape` returns NULL when the window has no
frame to read, and `apply` then keeps the blur and reads the next frame.
Without it a window resized while its surface is frozen (hidden behind
another window, waiting for the compositor's frame callback) loses its blur
until the program restarts. Send the same change upstream before the next copy.

Remove this directory and depend on `bigstyle` once that package is published.
Any other change goes upstream first and is copied again.
