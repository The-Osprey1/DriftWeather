import os
import tarfile
import shutil

backup_path = "/home/user/G4Cast_Backup.tar.gz"
staging_dir = "/home/user/g4cast_staging/G4Cast"

if os.path.exists("/home/user/g4cast_staging"):
    shutil.rmtree("/home/user/g4cast_staging")

os.makedirs(staging_dir, exist_ok=True)
os.makedirs(f"{staging_dir}/fonts", exist_ok=True)

# Copy core files and modular packages
shutil.copy("/home/user/G4Cast/G4Cast.py", f"{staging_dir}/G4Cast.py")
shutil.copy("/home/user/G4Cast/main.py", f"{staging_dir}/main.py")
shutil.copy("/home/user/G4Cast/switch_theme.py", f"{staging_dir}/switch_theme.py")
shutil.copy("/home/user/G4Cast/validate_all.py", f"{staging_dir}/validate_all.py")
shutil.copy("/home/user/G4Cast/RESTORE.md", f"{staging_dir}/RESTORE.md")
shutil.copy("/etc/systemd/system/G4Cast.service", f"{staging_dir}/G4Cast.service")
if os.path.exists("/boot/firmware/G4Cast/G4CastData.txt"):
    shutil.copy("/boot/firmware/G4Cast/G4CastData.txt", f"{staging_dir}/G4CastData.txt")

# Copy modular packages
for pkg in ("config", "display", "weather", "services", "web", "docs"):
    pkg_path = f"/home/user/G4Cast/{pkg}"
    if os.path.exists(pkg_path):
        shutil.copytree(pkg_path, f"{staging_dir}/{pkg}", dirs_exist_ok=True)

# Copy icons
if os.path.exists("/home/user/G4Cast/pic"):
    shutil.copytree("/home/user/G4Cast/pic", f"{staging_dir}/pic", dirs_exist_ok=True)

# Copy fonts
font_dir = "/usr/share/fonts/opentype/inter"
if os.path.exists(font_dir):
    for f in os.listdir(font_dir):
        if f.endswith(".otf"):
            shutil.copy(os.path.join(font_dir, f), f"{staging_dir}/fonts/{f}")

# Create tar.gz
with tarfile.open(backup_path, "w:gz") as tar:
    tar.add(staging_dir, arcname="G4Cast")

shutil.rmtree("/home/user/g4cast_staging")
size_kb = os.path.getsize(backup_path) / 1024
print(f"Created {backup_path} ({size_kb:.1f} KB)")
