"""Đưa IPA lên GitHub Releases và cập nhật apps.json (nguồn SideStore/AltStore).

    py -3 release.py                    # cả 4 IPA mặc định bên dưới
    py -3 release.py path/to/App.ipa    # chỉ những IPA chỉ định

Cần: gh đã đăng nhập (gh auth login), thư mục này là clone của repo công khai REPO.
"""
import datetime, json, os, plistlib, subprocess, sys, zipfile

sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252, in tiếng Việt sẽ lỗi
REPO = "PastieVietNam/PastieChat-Releases"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_IPAS = [
    "pastie-superadmin-ios/PastieAdmin-Production.ipa",
    "pastie-superadmin-ios/PastieAdmin-Staging.ipa",
    "pastie-staff-ios/PastieStaff-Production.ipa",
    "pastie-staff-ios/PastieStaff-Staging.ipa",
]
ICON = f"https://raw.githubusercontent.com/{REPO}/main/icon.png"
ABOUT = {
    "com.pastiechat.superadmin": "Bảng điều khiển Superadmin của Pastie Chat.",
    "com.pastiechat.staff": "Ứng dụng cho Agent và Sale của Pastie Chat.",
}
KEEP = 5  # số bản giữ lại trong apps.json cho mỗi app


def read_ipa(path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.count("/") == 2 and n.endswith(".app/Info.plist"))
        info = plistlib.loads(z.read(name))
    return info


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def release(path, source):
    info = read_ipa(path)
    bid, ver, build = info["CFBundleIdentifier"], info["CFBundleShortVersionString"], info.get("CFBundleVersion", "1")
    tag = f"{bid}-{ver}-{build}"
    file = os.path.basename(path)
    print(f"→ {file}: {bid} {ver} ({build})")

    if gh("release", "view", tag, "--repo", REPO).returncode == 0:
        r = gh("release", "upload", tag, path, "--clobber", "--repo", REPO)
    else:
        r = gh("release", "create", tag, path, "--repo", REPO, "--title", f"{info.get('CFBundleDisplayName', bid)} {ver}",
               "--notes", f"Build {build}")
    if r.returncode:
        sys.exit(f"LỖI gh: {r.stderr.strip()}")

    version = {
        "version": ver,
        "buildVersion": build,
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "localizedDescription": f"Build {build}",
        "downloadURL": f"https://github.com/{REPO}/releases/download/{tag}/{file}",
        "size": os.path.getsize(path),
        "minOSVersion": info.get("MinimumOSVersion", "17.0"),
    }
    app = next((a for a in source["apps"] if a["bundleIdentifier"] == bid), None)
    if app is None:
        app = {
            "name": info.get("CFBundleDisplayName", bid),
            "bundleIdentifier": bid,
            "developerName": "Pastie",
            "localizedDescription": ABOUT.get(bid.removesuffix(".staging"), "Pastie Chat")
                                    + (" Bản thử nghiệm (apitest)." if bid.endswith(".staging") else ""),
            "iconURL": ICON,
            "tintColor": "#3B82F6",
            "versions": [],
        }
        source["apps"].append(app)
    app["versions"] = [version] + [v for v in app["versions"] if v.get("buildVersion") != build][:KEEP - 1]
    # Trường cũ cho SideStore/AltStore bản trước 2.0.
    app.update({k: version[k] for k in ("version", "downloadURL", "size")}, versionDate=version["date"])


def main():
    ipas = sys.argv[1:] or [os.path.join(ROOT, p) for p in DEFAULT_IPAS if os.path.exists(os.path.join(ROOT, p))]
    src_path = os.path.join(HERE, "apps.json")
    with open(src_path, encoding="utf-8") as f:
        source = json.load(f)
    for p in ipas:
        release(p, source)
    with open(src_path, "w", encoding="utf-8") as f:
        json.dump(source, f, ensure_ascii=False, indent=2)
        f.write("\n")
    subprocess.run(["git", "-C", HERE, "add", "apps.json"], check=True)
    subprocess.run(["git", "-C", HERE, "commit", "-q", "-m", "release: " + ", ".join(map(os.path.basename, ipas))], check=True)
    subprocess.run(["git", "-C", HERE, "push", "-q"], check=True)
    print(f"Xong. Nguồn SideStore: https://raw.githubusercontent.com/{REPO}/main/apps.json")


if __name__ == "__main__":
    main()
