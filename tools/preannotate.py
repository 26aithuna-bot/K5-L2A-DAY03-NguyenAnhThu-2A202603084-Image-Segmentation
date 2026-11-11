"""Tạo GỢI Ý mask (pre-annotation) để import vào CVAT — KHÔNG phải bài nộp.

- Thing (person, car, bus, truck, motorcycle, bicycle, traffic light): YOLO-seg (COCO).
- Stuff / semantic (road, sidewalk, building, vegetation, sky, pole, traffic sign, ...):
  SegFormer huấn luyện trên Cityscapes.

Đầu ra: preannotations/<task>.json (COCO 1.0, mask RLE) để CVAT → Job → Menu →
Upload annotations → COCO 1.0. Sau khi import, người học PHẢI tự kiểm class,
số object, biên, vùng bỏ sót và sửa bằng Brush/Eraser trước khi Save/export.

Chế độ --merge-with: giữ nguyên các object đã tự vẽ trong một bản export COCO
của CVAT và chỉ thêm các gợi ý không trùng (IoU < 0.5), để upload không làm mất
object tự vẽ đầu tiên của Medium.

Ví dụ:
  python tools/preannotate.py --all
  python tools/preannotate.py --task hard_panoptic --preview
  python tools/preannotate.py --task medium_instance --merge-with medium_manual.zip
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "preannotations"

YOLO_WEIGHTS = "yolo11x-seg.pt"
SEGFORMER = "nvidia/segformer-b2-finetuned-cityscapes-1024-1024"
THING_NAMES = {"person", "bicycle", "car", "motorcycle", "bus", "truck", "traffic light"}
MIN_AREA = 150  # px: bỏ mảnh vụn


# --------------------------------------------------------------------------- utils
def rle_encode_fast(mask: np.ndarray) -> dict:
    """Uncompressed COCO RLE (column-major), counts bắt đầu bằng số pixel 0."""
    flat = mask.astype(np.uint8).flatten(order="F")
    change = np.flatnonzero(np.diff(flat)) + 1
    bounds = np.concatenate([[0], change, [flat.size]])
    runs = np.diff(bounds).tolist()
    if flat.size and flat[0] == 1:
        runs = [0] + runs
    return {"counts": [int(r) for r in runs], "size": [int(mask.shape[0]), int(mask.shape[1])]}


def bbox_of(mask: np.ndarray) -> list[float]:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return [0, 0, 0, 0]
    return [float(xs.min()), float(ys.min()), float(xs.max() - xs.min() + 1), float(ys.max() - ys.min() + 1)]


def clean(mask: np.ndarray) -> np.ndarray:
    import cv2
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    keep = np.zeros_like(mask, dtype=bool)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= MIN_AREA:
            keep |= lab == i
    return keep


def task_info(name: str) -> tuple[dict, dict, list[Path]]:
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))["tasks"]
    info = manifest[name]
    folder = DATA / info["path"]
    classes = json.loads((folder / "classes.json").read_text(encoding="utf-8"))
    images = sorted(p for p in (folder / "images").iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    return info, classes, images


# --------------------------------------------------------------------------- models
_yolo = None
_seg = None


def yolo_instances(img_path: Path, wanted: set[str], conf: float) -> list[tuple[str, np.ndarray, float]]:
    global _yolo
    from ultralytics import YOLO
    if _yolo is None:
        _yolo = YOLO(YOLO_WEIGHTS)
    res = _yolo.predict(str(img_path), conf=conf, retina_masks=True, verbose=False, device="cpu")[0]
    out = []
    if res.masks is None:
        return out
    names = res.names
    for m, c, s in zip(res.masks.data.cpu().numpy(), res.boxes.cls.cpu().numpy(), res.boxes.conf.cpu().numpy()):
        cls = names[int(c)]
        if cls not in wanted:
            continue
        mask = clean(m > 0.5)
        if mask.sum() >= MIN_AREA:
            out.append((cls, mask, float(s)))
    return out


def segformer_map(img_path: Path) -> tuple[np.ndarray, dict[int, str]]:
    global _seg
    import torch
    from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
    if _seg is None:
        _seg = (SegformerImageProcessor.from_pretrained(SEGFORMER),
                SegformerForSemanticSegmentation.from_pretrained(SEGFORMER).eval())
    proc, model = _seg
    img = Image.open(img_path).convert("RGB")
    with torch.no_grad():
        logits = model(**proc(images=img, return_tensors="pt")).logits
        logits = torch.nn.functional.interpolate(logits, size=img.size[::-1], mode="bilinear", align_corners=False)
    return logits.argmax(1)[0].numpy(), model.config.id2label


def semantic_masks(img_path: Path, wanted: list[str]) -> dict[str, np.ndarray]:
    pred, id2label = segformer_map(img_path)
    out = {}
    for idx, name in id2label.items():
        if name in wanted:
            m = clean(pred == int(idx))
            if m.sum() >= MIN_AREA:
                out[name] = m
    return out


# --------------------------------------------------------------------------- build
def build(name: str, conf: float) -> dict:
    info, classes, images = task_info(name)
    kind, names = info["type"], classes["classes"]
    cats = [{"id": i + 1, "name": n, "supercategory": ""} for i, n in enumerate(names)]
    cid = {c["name"]: c["id"] for c in cats}
    coco = {"info": {"description": f"PRE-ANNOTATION SUGGESTIONS for {name} — review before use"},
            "licenses": [], "categories": cats, "images": [], "annotations": []}
    ann_id = 1
    for img_id, path in enumerate(images, start=1):
        w, h = Image.open(path).size
        coco["images"].append({"id": img_id, "file_name": path.name, "width": w, "height": h})
        items: list[tuple[str, np.ndarray, float]] = []
        if kind in {"instance", "panoptic"}:
            items += yolo_instances(path, set(names) & THING_NAMES, conf)
        if kind == "panoptic":
            things = np.zeros((h, w), bool)
            for _, m, _ in items:
                things |= m
            stuff = semantic_masks(path, classes.get("stuff", []))
            items += [(n, clean(m & ~things), 1.0) for n, m in stuff.items()]
        if kind == "semantic":
            items += [(n, m, 1.0) for n, m in semantic_masks(path, names).items()]
        for cls, mask, score in items:
            if mask.sum() < MIN_AREA:
                continue
            coco["annotations"].append({
                "id": ann_id, "image_id": img_id, "category_id": cid[cls], "iscrowd": 1,
                "segmentation": rle_encode_fast(mask), "area": float(mask.sum()),
                "bbox": bbox_of(mask), "attributes": {"occluded": False, "score": round(score, 3)},
            })
            ann_id += 1
        print(f"  {path.name}: {sum(1 for a in coco['annotations'] if a['image_id'] == img_id)} gợi ý")
    return coco


# --------------------------------------------------------------------------- merge
def _decode(seg, h, w) -> np.ndarray:
    from pycocotools import mask as cm
    if isinstance(seg, list):
        rle = cm.merge(cm.frPyObjects(seg, h, w))
    elif isinstance(seg.get("counts"), list):
        rle = cm.frPyObjects(seg, h, w)
    else:
        rle = seg
    return cm.decode(rle).astype(bool)


def merge(suggest: dict, export_zip: Path) -> dict:
    with zipfile.ZipFile(export_zip) as z:
        key = sorted((k for k in z.namelist() if k.endswith(".json")), key=len)[0]
        manual = json.loads(z.read(key).decode("utf-8"))
    m_cats = {c["id"]: c["name"] for c in manual["categories"]}
    m_imgs = {im["id"]: im for im in manual["images"]}
    s_cid = {c["name"]: c["id"] for c in suggest["categories"]}
    s_img = {Path(im["file_name"]).name: im for im in suggest["images"]}
    out = dict(suggest, annotations=[])
    manual_masks: dict[int, list[np.ndarray]] = {}
    ann_id = 1
    for a in manual["annotations"]:
        im = m_imgs[a["image_id"]]
        target = s_img[Path(im["file_name"]).name]
        mask = _decode(a["segmentation"], im["height"], im["width"])
        manual_masks.setdefault(target["id"], []).append(mask)
        out["annotations"].append(dict(a, id=ann_id, image_id=target["id"], category_id=s_cid[m_cats[a["category_id"]]]))
        ann_id += 1
    kept = 0
    for a in suggest["annotations"]:
        im = next(i for i in suggest["images"] if i["id"] == a["image_id"])
        m = _decode(a["segmentation"], im["height"], im["width"])
        if any((m & mm).sum() / max((m | mm).sum(), 1) >= 0.5 for mm in manual_masks.get(a["image_id"], [])):
            continue
        out["annotations"].append(dict(a, id=ann_id))
        ann_id += 1
        kept += 1
    print(f"  giữ {len(manual['annotations'])} object tự vẽ + {kept} gợi ý không trùng")
    return out


# --------------------------------------------------------------------------- preview
def preview(name: str, coco: dict) -> None:
    _, classes, images = task_info(name)
    colors = {k: tuple(v) for k, v in classes.get("colors", {}).items()}
    cats = {c["id"]: c["name"] for c in coco["categories"]}
    rng = np.random.default_rng(0)
    folder = OUT / "preview" / name
    folder.mkdir(parents=True, exist_ok=True)
    for im in coco["images"]:
        path = next(p for p in images if p.name == im["file_name"])
        base = np.asarray(Image.open(path).convert("RGB")).astype(float)
        over = base.copy()
        for a in (x for x in coco["annotations"] if x["image_id"] == im["id"]):
            m = _decode(a["segmentation"], im["height"], im["width"])
            col = np.array(colors.get(cats[a["category_id"]], rng.integers(0, 255, 3)), float)
            if cats[a["category_id"]] in THING_NAMES and classes["type"] != "semantic":
                col = rng.integers(40, 255, 3).astype(float)  # mỗi instance một màu
            over[m] = 0.45 * base[m] + 0.55 * col
        Image.fromarray(over.astype(np.uint8)).save(folder / f"{path.stem}.jpg", quality=88)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--task")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--merge-with", type=Path, help="ZIP COCO 1.0 export từ CVAT chứa object tự vẽ")
    ap.add_argument("--preview", action="store_true", help="lưu ảnh overlay vào preannotations/preview/")
    args = ap.parse_args()
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))["tasks"]
    tasks = list(manifest) if args.all else [args.task]
    OUT.mkdir(exist_ok=True)
    for name in tasks:
        print(f"[{name}]")
        coco = build(name, args.conf)
        suffix = ""
        if args.merge_with:
            coco = merge(coco, args.merge_with)
            suffix = "_merged"
        dest = OUT / f"{name}{suffix}.json"
        dest.write_text(json.dumps(coco), encoding="utf-8")
        print(f"  -> {dest.relative_to(ROOT)}")
        if args.preview:
            preview(name, coco)


if __name__ == "__main__":
    main()
