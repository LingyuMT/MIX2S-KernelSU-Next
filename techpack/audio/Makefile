# Polaris audio integration changes: 2026-10-13/14; see build-support/CHANGES.md.
# Use USERINCLUDE when you must reference the UAPI directories only.
USERINCLUDE     += \
                -I$(srctree)/techpack/audio/include/uapi \

# Use LINUXINCLUDE when you must reference the include/ directory.
# Needed to be compatible with the O= option
LINUXINCLUDE    += \
                -I$(srctree)/techpack/audio/include/uapi \
                -I$(srctree)/techpack/audio/include

obj-y += asoc/
obj-y += dsp/
obj-y += ipc/
obj-y += soc/

subdir-ccflags-y += -include $(srctree)/techpack/audio/config/sdm845autoconf.h

subdir-ccflags-y += -I$(srctree)/techpack/audio
