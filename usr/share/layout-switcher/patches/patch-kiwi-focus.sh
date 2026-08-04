#!/usr/bin/env bash
#
# patch-kiwi-focus.sh — make Kiwi's demands-attention focus behavior optional.
#
# Upstream Kiwi always connects window-demands-attention to Main.activateWindow,
# so notifications can raise an existing application over the active window.
# Add a GSettings switch that layouts can disable without losing other Kiwi
# features. Re-applied by the pacman hook after Kiwi upgrades.
set -euo pipefail

KIWI_DIR="${LAYOUT_SWITCHER_KIWI_DIR:-/usr/share/gnome-shell/extensions/kiwi@kemma}"
EXTENSION_JS="${KIWI_DIR}/extension.js"
SCHEMA_XML="${KIWI_DIR}/schemas/org.gnome.shell.extensions.kiwi.gschema.xml"

[ -f "$EXTENSION_JS" ] || exit 0
[ -f "$SCHEMA_XML" ] || exit 0

python3 - "$EXTENSION_JS" "$SCHEMA_XML" <<'PYEOF'
import sys

extension_path, schema_path = sys.argv[1:]
extension = open(extension_path, encoding="utf-8").read()
schema = open(schema_path, encoding="utf-8").read()
original_extension = extension
original_schema = schema

marker = "ls-kiwi-focus-policy"
username_block = (
    "        if (this._settings.get_boolean('add-username-to-quick-menu')) {\n"
    "            addUsernameEnable();\n"
    "        } else {\n"
    "            addUsernameDisable();\n"
    "        }\n"
)
focus_block = (
    "\n"
    "        if (this._settings.get_boolean('focus-launched-windows')) { // ls-kiwi-focus-policy\n"
    "            focusLaunchedWindowEnable();\n"
    "        } else {\n"
    "            focusLaunchedWindowDisable();\n"
    "        }\n"
)
unconditional_focus = "        focusLaunchedWindowEnable();\n"

username_schema = (
    "      <key name=\"add-username-to-quick-menu\" type=\"b\">\n"
    "        <default>true</default>\n"
    "        <summary>Add Username to Quick Menu</summary>\n"
    "        <description>Enable or disable adding the username to the quick menu.</description>\n"
    "      </key>\n"
)
focus_schema = (
    "      <key name=\"focus-launched-windows\" type=\"b\">\n"
    "        <default>true</default>\n"
    "        <summary>Focus Launched Windows</summary>\n"
    "        <description>Focus windows that demand attention instead of showing only a notification.</description>\n"
    "      </key>\n"
)

if marker not in extension:
    if username_block not in extension or unconditional_focus not in extension:
        print(
            "layout-switcher: WARNING Kiwi focus patch NOT applied "
            "(upstream code changed shape)",
            file=sys.stderr,
        )
        raise SystemExit(0)
    extension = extension.replace(unconditional_focus, "", 1)
    extension = extension.replace(username_block, username_block + focus_block, 1)

if 'name="focus-launched-windows"' not in schema:
    if username_schema not in schema:
        print(
            "layout-switcher: WARNING Kiwi focus schema patch NOT applied "
            "(upstream schema changed shape)",
            file=sys.stderr,
        )
        raise SystemExit(0)
    schema = schema.replace(username_schema, username_schema + focus_schema, 1)

if extension != original_extension:
    open(extension_path, "w", encoding="utf-8").write(extension)
if schema != original_schema:
    open(schema_path, "w", encoding="utf-8").write(schema)

if extension != original_extension or schema != original_schema:
    print("layout-switcher: added per-layout Kiwi focus policy")
PYEOF

glib-compile-schemas "${KIWI_DIR}/schemas"
