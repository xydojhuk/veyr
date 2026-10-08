#!/usr/bin/bash

set -Eeuo pipefail

export PATH=/usr/bin:/usr/sbin:/bin:/sbin
unset LD_LIBRARY_PATH

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

echo "Veyr alpha.4 native chroot tool test"
echo "===================================="

if ! grep -Eq '^/dev/vda / ext4 ' /proc/mounts; then
    echo "Current root mounts:" >&2
    grep ' / ' /proc/mounts >&2 || true
    fail "root filesystem is not /dev/vda ext4"
fi

echo "OK: root filesystem is /dev/vda (ext4)"

[[ ! -e /init ]] || fail "old initramfs /init is still visible after switch_root"
echo "OK: old initramfs root was discarded"

[[ -s /etc/ld.so.cache ]] || fail "/etc/ld.so.cache is missing"
echo "OK: dynamic loader cache exists"

[[ "$(cat /etc/veyr-stage 2>/dev/null)" == "alpha4-native-complete" ]] \
    || fail "alpha.4 completion marker is missing"
echo "OK: alpha.4 completion marker exists"

required_commands=(
    /usr/bin/bash
    /usr/bin/gcc
    /usr/bin/g++
    /usr/bin/make
    /usr/bin/msgfmt
    /usr/bin/msgmerge
    /usr/bin/xgettext
    /usr/bin/bison
    /usr/bin/perl
    /usr/bin/python3
    /usr/bin/makeinfo
    /usr/bin/lsblk
    /usr/bin/mount
    /usr/bin/readelf
)

for command_path in "${required_commands[@]}"; do
    [[ -x "${command_path}" ]] || fail "missing ${command_path}"
    echo "OK: ${command_path}"
done

TARGET=x86_64-veyr-linux-gnu

[[ "$(gcc -dumpmachine)" == "${TARGET}" ]] \
    || fail "gcc target is not ${TARGET}"
[[ "$(g++ -dumpmachine)" == "${TARGET}" ]] \
    || fail "g++ target is not ${TARGET}"

echo "OK: GCC target is ${TARGET}"

echo
echo "Native build provenance:"

native_packages=(
    gettext-native
    bison-native
    perl-native
    zlib-native
    mpdecimal-native
    python-native
    texinfo-native
    util-linux-native
)

for package in "${native_packages[@]}"; do
    marker="/usr/lib/veyr/native-build/${package}.stamp"

    [[ -f "${marker}" ]] || fail "missing native-build marker ${marker}"
    grep -qx 'environment=chroot' "${marker}" \
        || fail "${package} was not marked as a chroot build"
    grep -qx "compiler=${TARGET}" "${marker}" \
        || fail "${package} marker has an unexpected compiler target"

    echo "OK: ${package} was built inside the Veyr chroot"
done

echo
echo "Tool versions:"
msgfmt --version
bison --version
perl -v
python3 --version
makeinfo --version
lsblk --version

echo
echo "Testing Gettext..."
TEST_DIR=/tmp/veyr-alpha4-test
rm -rf "${TEST_DIR}"
mkdir -p "${TEST_DIR}"

cat > "${TEST_DIR}/veyr.po" <<'EOF_PO'
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"

msgid "hello"
msgstr "veyr"
EOF_PO

msgfmt "${TEST_DIR}/veyr.po" -o "${TEST_DIR}/veyr.mo"
[[ -s "${TEST_DIR}/veyr.mo" ]] || fail "msgfmt did not create a .mo file"
echo "Gettext functional test: OK"

echo
echo "Testing Bison..."
cat > "${TEST_DIR}/parser.y" <<'EOF_Y'
%{
int yylex(void) { return 0; }
void yyerror(const char *s) { (void)s; }
%}
%%
input: ;
%%
int main(void) { return yyparse(); }
EOF_Y

bison -o "${TEST_DIR}/parser.c" "${TEST_DIR}/parser.y"
gcc -O2 -Wall -Wextra "${TEST_DIR}/parser.c" -o "${TEST_DIR}/parser"
"${TEST_DIR}/parser"
echo "Bison functional test: OK"

echo
echo "Testing Perl..."
perl -e 'print "Veyr Perl runtime: OK\n"'

echo
echo "Testing Zlib C development files..."
cat > "${TEST_DIR}/zlib-test.c" <<'EOF_C'
#include <stdio.h>
#include <zlib.h>

int main(void)
{
    printf("Veyr Zlib runtime: %s\n", zlibVersion());
    return 0;
}
EOF_C

gcc -O2 -Wall -Wextra "${TEST_DIR}/zlib-test.c" -lz -o "${TEST_DIR}/zlib-test"
"${TEST_DIR}/zlib-test"

echo
echo "Testing Python, mpdecimal and zlib modules..."
python3 - <<'EOF_PY'
import decimal
import sys
import zlib

if sys.prefix != "/usr":
    raise SystemExit(f"unexpected Python prefix: {sys.prefix}")

value = decimal.Decimal("1.25") + decimal.Decimal("2.75")
if value != decimal.Decimal("4.00"):
    raise SystemExit("decimal module produced an unexpected result")

payload = zlib.decompress(zlib.compress(b"Veyr alpha.4"))
if payload != b"Veyr alpha.4":
    raise SystemExit("zlib module roundtrip failed")

print("Veyr Python runtime: OK")
print("Python prefix: /usr")
print("Python decimal module: OK")
print("Python zlib module: OK")
EOF_PY

echo
echo "Python ELF interpreter:"
readelf -l /usr/bin/python3 \
    | grep 'Requesting program interpreter'

echo
echo "Testing Texinfo..."
cat > "${TEST_DIR}/sample.texi" <<'EOF_TEXI'
\input texinfo
@setfilename veyr.info
@node Top
@top Veyr alpha.4
Native chroot tooling test.
@bye
EOF_TEXI

makeinfo "${TEST_DIR}/sample.texi" -o "${TEST_DIR}/veyr.info"
[[ -s "${TEST_DIR}/veyr.info" ]] || fail "makeinfo did not create output"
echo "Texinfo functional test: OK"

echo
echo "Testing Util-linux..."
lsblk --version
mount --version

echo
echo "Disk root is writable..."
echo 'alpha4-disk-write-ok' > "${TEST_DIR}/disk-write"
grep -qx 'alpha4-disk-write-ok' "${TEST_DIR}/disk-write" \
    || fail "disk-backed root write verification failed"
echo "OK: disk-backed root is writable"

echo
echo "Native chroot tool verification: PASS"