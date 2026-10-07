# Migood OS in a virtual machine, inside Docker (for a Codespace or any Linux PC).
# It uses qemux/qemu: QEMU in a container that shows the VM's screen in your
# browser at http://localhost:8006.
#
# Easiest: from the repo root run   bash vm/start.sh
# (downloads the newest ISO from Releases, then starts this with docker compose).
FROM qemux/qemu

# The VM: 6 GB RAM, 4 CPU cores, a 40 GB virtual disk to install Migood OS onto.
ENV RAM_SIZE="6G" \
    CPU_CORES="4" \
    DISK_SIZE="40G"

# The ISO is not baked in (4 GB); docker-compose.yml mounts it at /boot.iso.
