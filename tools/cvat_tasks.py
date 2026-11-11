"""Tự động hóa thao tác lặp lại trên CVAT local (http://localhost:8080) bằng cvat-sdk.

  setup         tạo 9 task (đúng tên, label từ cvat-labels.json, ảnh trong data/)
                và import gợi ý preannotations/<task>.json — TRỪ medium_instance
                (Medium phải tự vẽ object đầu tiên trước khi xem gợi ý).
  merge-medium  sau khi đã tự vẽ + Save object đầu ở Medium: export bản đang có,
                trộn với gợi ý YOLO (bỏ gợi ý trùng IoU>=0.5) rồi import lại.
  export        sau khi ĐÃ TỰ KIỂM/SỬA và Save trong CVAT: export từng task
                đúng format vào submissions/<task>.zip.
  status        liệt kê task và số annotation hiện có.

Đăng nhập: biến môi trường CVAT_ACCESS_TOKEN, hoặc script hỏi username/password
(password nhập ẩn bằng getpass, không lưu ra file).

  ..\\.venv-day3\\Scripts\\python.exe tools\\cvat_tasks.py setup
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

from cvat_sdk import make_client, models

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PRE = ROOT / "preannotations"
SUB = ROOT / "submissions"
HOST = os.environ.get("CVAT_HOST", "http://localhost:8080")
EXPORT_FORMAT = {"semantic": "Segmentation mask 1.1", "instance": "COCO 1.0", "panoptic": "COCO 1.0"}
NO_AUTO_IMPORT = {"medium_instance"}


def manifest() -> dict:
    return json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))["tasks"]


def connect():
    token = os.environ.get("CVAT_ACCESS_TOKEN")
    if token:
        return make_client(HOST, access_token=token)
    user = os.environ.get("CVAT_USER") or input("CVAT username: ").strip()
    password = os.environ.get("CVAT_PASS") or getpass.getpass("CVAT password (ẩn): ")
    return make_client(HOST, credentials=(user, password))


def tasks_by_name(client) -> dict:
    return {t.name: t for t in client.tasks.list()}


def import_json(task, path: Path) -> None:
    task.import_annotations("COCO 1.0", str(path), conv_mask_to_poly=False)


def cmd_setup(client, only: list[str] | None) -> None:
    existing = tasks_by_name(client)
    for name, info in manifest().items():
        if only and name not in only:
            continue
        folder = DATA / info["path"]
        if name in existing:
            print(f"[{name}] đã có task #{existing[name].id} — bỏ qua tạo mới")
            continue
        labels = json.loads((folder / "cvat-labels.json").read_text(encoding="utf-8"))
        images = sorted(str(p) for p in (folder / "images").glob("*.jpg"))
        spec = models.TaskWriteRequest(name=name, labels=[models.PatchedLabelRequest(**{
            k: v for k, v in lab.items() if k in {"name", "color", "type", "attributes"}}) for lab in labels])
        task = client.tasks.create_from_data(spec=spec, resources=images,
                                             data_params={"image_quality": 95, "sorting_method": "lexicographical"})
        print(f"[{name}] tạo task #{task.id}: {len(labels)} label, {len(images)} ảnh")
        pre = PRE / f"{name}.json"
        if name in NO_AUTO_IMPORT:
            print(f"[{name}] KHÔNG import gợi ý: tự vẽ object đầu tiên trước (RULES)")
        elif pre.exists():
            import_json(task, pre)
            print(f"[{name}] đã import gợi ý {pre.relative_to(ROOT)} — cần tự kiểm/sửa")
        else:
            print(f"[{name}] chưa có {pre.name}; chạy tools/preannotate.py trước nếu muốn gợi ý")


def cmd_merge_medium(client) -> None:
    sys.path.insert(0, str(ROOT / "tools"))
    import preannotate as pa
    task = tasks_by_name(client)["medium_instance"]
    with tempfile.TemporaryDirectory() as tmp:
        manual = Path(tmp) / "medium_manual.zip"
        task.export_dataset("COCO 1.0", str(manual), include_images=False)
        with zipfile.ZipFile(manual) as z:
            key = next(k for k in z.namelist() if k.endswith(".json"))
            n = len(json.loads(z.read(key))["annotations"])
        if n == 0:
            sys.exit("medium_instance chưa có object nào. Hãy tự vẽ object đầu tiên và Save trước.")
        print(f"[medium_instance] giữ {n} object tự vẽ; đang tạo gợi ý YOLO…")
        merged = pa.merge(pa.build("medium_instance", 0.35), manual)
    PRE.mkdir(exist_ok=True)
    out = PRE / "medium_instance_merged.json"
    out.write_text(json.dumps(merged), encoding="utf-8")
    import_json(task, out)
    print(f"[medium_instance] đã import {out.relative_to(ROOT)} — cần tự kiểm/sửa")


def cmd_export(client, only: list[str] | None) -> None:
    SUB.mkdir(exist_ok=True)
    existing = tasks_by_name(client)
    for name, info in manifest().items():
        if only and name not in only:
            continue
        if name not in existing:
            print(f"[{name}] chưa có task — bỏ qua (không tạo ZIP rỗng)")
            continue
        task = existing[name]
        if not task.get_annotations().shapes:
            print(f"[{name}] task chưa có annotation — bỏ qua (không tạo ZIP rỗng)")
            continue
        dest = SUB / f"{name}.zip"
        tmp = dest.with_suffix(".zip.part")
        tmp.unlink(missing_ok=True)
        task.export_dataset(EXPORT_FORMAT[info["type"]], str(tmp), include_images=False)
        tmp.replace(dest)  # ghi đè bản export cũ sau khi tải xong
        print(f"[{name}] -> {dest.relative_to(ROOT)} ({EXPORT_FORMAT[info['type']]})")


def cmd_status(client) -> None:
    for name, task in sorted(tasks_by_name(client).items()):
        shapes = task.get_annotations().shapes
        print(f"#{task.id:<4} {name:<16} {task.size} ảnh, {len(shapes)} shape, jobs={[j.id for j in task.get_jobs()]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["setup", "merge-medium", "export", "status"])
    ap.add_argument("--only", nargs="*", help="chỉ xử lý các task này")
    args = ap.parse_args()
    with connect() as client:
        {"setup": lambda: cmd_setup(client, args.only),
         "merge-medium": lambda: cmd_merge_medium(client),
         "export": lambda: cmd_export(client, args.only),
         "status": lambda: cmd_status(client)}[args.command]()


if __name__ == "__main__":
    main()
