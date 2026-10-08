SHELL := /usr/bin/env bash

.PHONY: all
all: alpha4

.PHONY: deps
deps:
	./scripts/setup-fedora.sh

.PHONY: doctor
doctor:
	./veyr doctor

.PHONY: check
check:
	./veyr check

.PHONY: list
list:
	./veyr list packages
	@echo
	./veyr list profiles

.PHONY: graph
graph:
	./veyr graph base-alpha4

.PHONY: bootstrap-graph
bootstrap-graph:
	./veyr graph bootstrap

.PHONY: alpha1-graph
alpha1-graph:
	./veyr graph base-alpha1

.PHONY: alpha2-graph
alpha2-graph:
	./veyr graph base-alpha2

.PHONY: alpha3-graph
alpha3-graph:
	./veyr graph base-alpha3

.PHONY: alpha4-graph
alpha4-graph:
	./veyr graph base-alpha4

.PHONY: fetch
fetch:
	./veyr fetch --profile base-alpha4

.PHONY: busybox
busybox:
	./veyr build busybox

.PHONY: kernel
kernel:
	./veyr build linux

.PHONY: bootstrap
bootstrap:
	./veyr image bootstrap

.PHONY: bootstrap-run
bootstrap-run:
	./veyr run bootstrap

.PHONY: toolchain
toolchain:
	./veyr build --profile toolchain-alpha1

.PHONY: toolchain-test
toolchain-test: toolchain
	./scripts/build-toolchain-test.sh

.PHONY: alpha1
alpha1:
	./veyr image base-alpha1

.PHONY: run-alpha1
run-alpha1:
	./veyr run base-alpha1

.PHONY: temporary
temporary:
	./veyr build --profile temporary-alpha2

.PHONY: userspace-test
userspace-test: temporary
	./scripts/build-userspace-test.sh

.PHONY: alpha2
alpha2:
	./veyr image base-alpha2

.PHONY: run-alpha2
run-alpha2:
	./veyr run base-alpha2

.PHONY: alpha3-rootfs
alpha3-rootfs:
	./scripts/build-alpha3-rootfs.sh

.PHONY: alpha3-initramfs
alpha3-initramfs:
	./scripts/build-alpha3-initramfs.sh

.PHONY: alpha3
alpha3:
	./veyr image base-alpha3

.PHONY: run-alpha3
run-alpha3:
	./veyr run base-alpha3

.PHONY: run-alpha3-serial
run-alpha3-serial:
	./scripts/run-alpha3-serial.sh

.PHONY: chroot-alpha3
chroot-alpha3:
	./scripts/chroot-alpha3.sh

.PHONY: alpha4-temporary
alpha4-temporary:
	./veyr build --profile temporary-alpha4

.PHONY: alpha4
alpha4:
	./veyr image base-alpha4

.PHONY: run
run:
	./veyr run base-alpha4

.PHONY: run-alpha4
run-alpha4:
	./veyr run base-alpha4

.PHONY: run-alpha4-serial
run-alpha4-serial:
	./scripts/run-alpha4-serial.sh

.PHONY: chroot-alpha4
chroot-alpha4:
	./scripts/chroot-alpha4.sh

.PHONY: clean
clean:
	./veyr clean

.PHONY: distclean
distclean:
	./veyr clean --sources