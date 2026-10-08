#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

ensure_dirs

PROFILE=base-alpha4
SYSROOT="${OUT_DIR}/sysroot"
BUSYBOX_BIN="${OUT_DIR}/packages/busybox/rootfs/bin/busybox"
ROOTFS_BUILD="${BUILD_DIR}/images/${PROFILE}/rootfs"
ROOT_INIT="${ROOT_DIR}/rootfs/alpha4/init"
SMOKE_TEST="${ROOT_DIR}/tests/native-alpha4/smoke.sh"

if (( EUID == 0 )); then
    SUDO=()
else
    require_command sudo
    SUDO=(sudo)
fi

[[ -d "${SYSROOT}/usr" ]] \
    || die "Temporary Veyr sysroot is missing. Build temporary-alpha2 first."

for binary in bash gcc g++ make env; do
    [[ -x "${SYSROOT}/usr/bin/${binary}" ]] \
        || die "Missing temporary Veyr tool: /usr/bin/${binary}"
done

[[ -x "${SYSROOT}/usr/sbin/ldconfig" ]] \
    || die "Static Veyr ldconfig is missing from sysroot"

[[ -e "${SYSROOT}/usr/lib/ld-linux-x86-64.so.2" ]] \
    || die "Veyr dynamic loader is missing from sysroot"

[[ -x "${BUSYBOX_BIN}" ]] \
    || die "Static BusyBox output is missing"

[[ -x "${ROOT_INIT}" ]] \
    || die "Alpha.4 root init is missing or not executable"

[[ -x "${SMOKE_TEST}" ]] \
    || die "Alpha.4 runtime smoke test is missing or not executable"

if ! file "${BUSYBOX_BIN}" | grep -qi 'statically linked'; then
    die "Alpha.4 rescue BusyBox must be statically linked"
fi

write_essential_accounts() {
    local rootfs="$1"
    local passwd_tmp
    local group_tmp

    mkdir -p "${rootfs}/etc"
    "${SUDO[@]}" mkdir -p "${rootfs}/var/log"

    passwd_tmp="$(mktemp)"
    group_tmp="$(mktemp)"

    cat > "${passwd_tmp}" <<'EOF_PASSWD'
root:x:0:0:root:/root:/usr/bin/bash
bin:x:1:1:bin:/dev/null:/usr/bin/false
daemon:x:6:6:Daemon User:/dev/null:/usr/bin/false
messagebus:x:18:18:D-Bus Message Daemon User:/run/dbus:/usr/bin/false
uuidd:x:80:80:UUID Generation Daemon User:/dev/null:/usr/bin/false
nobody:x:65534:65534:Unprivileged User:/dev/null:/usr/bin/false
EOF_PASSWD

    cat > "${group_tmp}" <<'EOF_GROUP'
root:x:0:
bin:x:1:daemon
sys:x:2:
kmem:x:3:
tape:x:4:
tty:x:5:
daemon:x:6:
floppy:x:7:
disk:x:8:
lp:x:9:
dialout:x:10:
audio:x:11:
video:x:12:
utmp:x:13:
clock:x:14:
cdrom:x:15:
adm:x:16:
messagebus:x:18:
input:x:24:
mail:x:34:
kvm:x:61:
uuidd:x:80:
wheel:x:97:
users:x:999:
nogroup:x:65534:
EOF_GROUP

    "${SUDO[@]}" install -m 0644 "${passwd_tmp}" "${rootfs}/etc/passwd"
    "${SUDO[@]}" install -m 0644 "${group_tmp}" "${rootfs}/etc/group"

    rm -f "${passwd_tmp}" "${group_tmp}"

    for log_file in btmp faillog lastlog wtmp; do
        if [[ ! -e "${rootfs}/var/log/${log_file}" ]]; then
            "${SUDO[@]}" touch "${rootfs}/var/log/${log_file}"
        fi
    done

    # Use numeric ids here. Host-side group names are irrelevant to the Veyr
    # chroot and may not exist on Fedora.
    "${SUDO[@]}" chown 0:13 "${rootfs}/var/log/lastlog"
    "${SUDO[@]}" chmod 0664 "${rootfs}/var/log/lastlog"
    "${SUDO[@]}" chown 0:13 "${rootfs}/var/log/btmp"
    "${SUDO[@]}" chmod 0600 "${rootfs}/var/log/btmp"
}

# Preserve a valid partial/native alpha.4 staging tree so a failed long chroot
# build can be resumed without rebuilding every earlier native package. A full
# `./veyr clean` still removes this tree and gives a deterministic fresh build.
if [[ -d "${ROOTFS_BUILD}" ]] \
    && [[ -x "${ROOTFS_BUILD}/usr/bin/bash" ]] \
    && [[ -x "${ROOTFS_BUILD}/usr/bin/gcc" ]] \
    && [[ -s "${ROOTFS_BUILD}/etc/ld.so.cache" ]]; then

    stage="$(cat "${ROOTFS_BUILD}/etc/veyr-stage" 2>/dev/null || true)"

    if [[ "${stage}" == "alpha4-chroot-prepared" \
        || "${stage}" == "alpha4-native-complete" ]]; then

        log "Refreshing alpha.4 essential users/groups for resume"
        write_essential_accounts "${ROOTFS_BUILD}"

        log "Refreshing alpha.4 runtime files for resume"
        "${SUDO[@]}" install -m 0755 \
            "${ROOT_INIT}" \
            "${ROOTFS_BUILD}/usr/libexec/veyr-alpha4-init"
        "${SUDO[@]}" install -m 0755 \
            "${SMOKE_TEST}" \
            "${ROOTFS_BUILD}/usr/lib/veyr-tests/native-alpha4-smoke.sh"

        log "Reusing existing alpha.4 chroot root filesystem"
        "${SCRIPT_DIR}/validate-alpha4-bootstrap-rootfs.sh" "${ROOTFS_BUILD}"
        success "Alpha.4 chroot root is ready for resume: ${ROOTFS_BUILD}"
        exit 0
    fi
fi

log "Preparing clean alpha.4 chroot root filesystem"

if [[ -e "${ROOTFS_BUILD}" ]]; then
    if ! rm -rf "${ROOTFS_BUILD}" 2>/dev/null; then
        warning "Root-owned alpha.4 staging files detected; using sudo for cleanup"
        "${SUDO[@]}" rm -rf "${ROOTFS_BUILD}"
    fi
fi

mkdir -p "${ROOTFS_BUILD}"

cp -a "${SYSROOT}/usr" "${ROOTFS_BUILD}/usr"

ln -s usr/bin "${ROOTFS_BUILD}/bin"
ln -s usr/lib "${ROOTFS_BUILD}/lib"
ln -s usr/sbin "${ROOTFS_BUILD}/sbin"

mkdir -p "${ROOTFS_BUILD}/lib64"
cp -L \
    "${SYSROOT}/usr/lib/ld-linux-x86-64.so.2" \
    "${ROOTFS_BUILD}/lib64/ld-linux-x86-64.so.2"
chmod 0755 "${ROOTFS_BUILD}/lib64/ld-linux-x86-64.so.2"
ln -sfn \
    ld-linux-x86-64.so.2 \
    "${ROOTFS_BUILD}/lib64/ld-lsb-x86-64.so.3"

mkdir -p \
    "${ROOTFS_BUILD}/dev/pts" \
    "${ROOTFS_BUILD}/dev/shm" \
    "${ROOTFS_BUILD}/proc" \
    "${ROOTFS_BUILD}/sys" \
    "${ROOTFS_BUILD}/run" \
    "${ROOTFS_BUILD}/tmp" \
    "${ROOTFS_BUILD}/root" \
    "${ROOTFS_BUILD}/etc/ld.so.conf.d" \
    "${ROOTFS_BUILD}/sources" \
    "${ROOTFS_BUILD}/var/lib/hwclock" \
    "${ROOTFS_BUILD}/var/log" \
    "${ROOTFS_BUILD}/usr/libexec" \
    "${ROOTFS_BUILD}/usr/lib/veyr/native-build" \
    "${ROOTFS_BUILD}/usr/lib/veyr-tests" \
    "${ROOTFS_BUILD}/usr/sbin"

chmod 1777 "${ROOTFS_BUILD}/tmp" "${ROOTFS_BUILD}/sources"
chmod 0700 "${ROOTFS_BUILD}/root"

cp "${BUSYBOX_BIN}" "${ROOTFS_BUILD}/usr/libexec/busybox"
chmod 0755 "${ROOTFS_BUILD}/usr/libexec/busybox"

cp "${ROOT_INIT}" "${ROOTFS_BUILD}/usr/libexec/veyr-alpha4-init"
chmod 0755 "${ROOTFS_BUILD}/usr/libexec/veyr-alpha4-init"
ln -sfn ../libexec/veyr-alpha4-init "${ROOTFS_BUILD}/usr/sbin/init"
ln -sfn ../libexec/busybox "${ROOTFS_BUILD}/usr/sbin/poweroff"
ln -sfn ../libexec/busybox "${ROOTFS_BUILD}/usr/sbin/reboot"

cp "${SMOKE_TEST}" "${ROOTFS_BUILD}/usr/lib/veyr-tests/native-alpha4-smoke.sh"
chmod 0755 "${ROOTFS_BUILD}/usr/lib/veyr-tests/native-alpha4-smoke.sh"

cp "${ROOT_DIR}/rootfs/common/etc/motd" "${ROOTFS_BUILD}/etc/motd"
sed \
    "s/@VERSION@/${VEYR_VERSION}/g" \
    "${ROOT_DIR}/rootfs/common/etc/os-release.in" \
    > "${ROOTFS_BUILD}/etc/os-release"

printf '%s\n' "${PROFILE}" > "${ROOTFS_BUILD}/etc/veyr-image-profile"
printf '%s\n' 'alpha4-chroot-prepared' > "${ROOTFS_BUILD}/etc/veyr-stage"
printf '%s\n' 'veyr' > "${ROOTFS_BUILD}/etc/hostname"

write_essential_accounts "${ROOTFS_BUILD}"

cat > "${ROOTFS_BUILD}/etc/nsswitch.conf" <<'EOF_NSSWITCH'
passwd: files
group: files
shadow: files
hosts: files dns
networks: files
EOF_NSSWITCH

cat > "${ROOTFS_BUILD}/etc/hosts" <<'EOF_HOSTS'
127.0.0.1 localhost
127.0.1.1 veyr
::1       localhost
EOF_HOSTS

cat > "${ROOTFS_BUILD}/etc/fstab" <<'EOF_FSTAB'
/dev/vda  /      ext4     defaults  0  1
proc      /proc  proc     nosuid,noexec,nodev  0  0
sysfs     /sys   sysfs    nosuid,noexec,nodev  0  0
devtmpfs  /dev   devtmpfs mode=0755,nosuid  0  0
tmpfs     /run   tmpfs    mode=0755,nosuid,nodev  0  0
tmpfs     /tmp   tmpfs    mode=1777,nosuid,nodev  0  0
EOF_FSTAB

ln -sfn /proc/self/mounts "${ROOTFS_BUILD}/etc/mtab"

cat > "${ROOTFS_BUILD}/etc/ld.so.conf" <<'EOF_LDSO'
/usr/lib
include /etc/ld.so.conf.d/*.conf
EOF_LDSO

TARGET_LDCONFIG="${ROOTFS_BUILD}/usr/sbin/ldconfig"
LDCONFIG_INFO="$(file "${TARGET_LDCONFIG}")"

if ! grep -Eqi 'static|statically linked' <<<"${LDCONFIG_INFO}"; then
    die "Veyr ldconfig must be static for alpha.4 root preparation"
fi

"${TARGET_LDCONFIG}" -r "${ROOTFS_BUILD}"

[[ -s "${ROOTFS_BUILD}/etc/ld.so.cache" ]] \
    || die "Failed to create alpha.4 /etc/ld.so.cache"

"${SCRIPT_DIR}/validate-alpha4-bootstrap-rootfs.sh" "${ROOTFS_BUILD}"

success "Alpha.4 chroot root prepared: ${ROOTFS_BUILD}"
