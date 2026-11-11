# Hướng dẫn làm bài Day 3 trên CVAT local v2.74.1 (có gợi ý YOLO/SegFormer)

> File này là sổ tay thao tác cá nhân. Đề bài gốc vẫn là [README.md](README.md), [RULES.md](RULES.md), [CHECKPOINTS.md](CHECKPOINTS.md).
> Quy định quan trọng: **tự tạo mask, tự kiểm, tự giải thích**. Gợi ý máy chỉ là điểm xuất phát; mọi mask phải được bạn mở ra kiểm, sửa và chịu trách nhiệm. Ghi đúng công cụ đã dùng vào report.

## 0. Tổng quan quy trình

```text
(1) Cài CVAT local + tạo 9 task  ──►  (2) Medium: TỰ VẼ object đầu trước, ghi chép
          │                                      │
          ▼                                      ▼
(3) Upload gợi ý preannotations/<task>.json  ──►  (4) Tự QC + sửa bằng Brush/Eraser + Save
          │
          ▼
(5) Export đúng format → submissions/<task>.zip ──► (6) Kiểm ZIP ──► (7) Điền report ──► (8) Push
```

| Task | Ảnh | Loại | File gợi ý để upload | Export | Điểm |
| --- | ---: | --- | --- | --- | ---: |
| `easy_semantic` | 3 | semantic | `preannotations/easy_semantic.json` | Segmentation mask 1.1 | 20 |
| `medium_instance` | 3 | instance | `preannotations/medium_instance_merged.json` (xem bước 2) | COCO 1.0 | 32 |
| `hard_panoptic` | 2 | panoptic | `preannotations/hard_panoptic.json` | COCO 1.0 | 30 |
| `cp1_holes` | 1 | instance | `preannotations/cp1_holes.json` | COCO 1.0 | 3 |
| `cp2_slice` | 1 | instance | `preannotations/cp2_slice.json` | COCO 1.0 | 3 |
| `cp5_occlusion` | 1 | instance | `preannotations/cp5_occlusion.json` | COCO 1.0 | 3 |
| `cp3_thin` | 1 | semantic | `preannotations/cp3_thin.json` | Segmentation mask 1.1 | 3 |
| `cp4_curb` | 1 | semantic | `preannotations/cp4_curb.json` | Segmentation mask 1.1 | 3 |
| `cp6_coverage` | 1 | semantic | `preannotations/cp6_coverage.json` | Segmentation mask 1.1 | 3 |

Thư mục `preannotations/` được tạo trên máy bằng `tools/preannotate.py` và **đã nằm trong `.gitignore`**, nên sẽ không bị đẩy lên fork.

**Mẹo:** mở sẵn file Notepad `ghi_chep.txt` (ngoài repo) để ghi ngay trong lúc vẽ: ảnh nào, vùng nào, sửa gì, phân vân gì. Report mục 2–4 lấy từ ghi chép này.

---

## 1. Cài CVAT local (theo `CVAT guide.txt` của Lab Coach, nhánh A. Windows)

Máy này đã được kiểm: Windows 11 Home 64-bit, RAM 15,7 GB (≥ 8 GB), Hypervisor đang bật, ổ C trống ~45 GB → **đủ điều kiện**. WSL và Docker **chưa cài**. Lab pin **CVAT Community v2.74.1**; không tự đổi tag, không sửa Compose, không dùng CVAT khác.

### 1.1 Cài WSL 2 + Ubuntu (cần quyền admin, có restart)

1. Bấm **Start**, gõ `PowerShell`, chuột phải **Windows PowerShell** → **Run as administrator**.
2. Dán lệnh rồi Enter:

   ```powershell
   wsl --install
   ```

3. Khi được yêu cầu, chọn **Restart now**. Sau khi máy mở lại, mở ứng dụng **Ubuntu** từ Start. Ubuntu sẽ hỏi username/password: tự đặt. Khi gõ password, màn hình không hiện ký tự gì là bình thường.
   - Nếu `wsl --install` báo không nhận lệnh: chạy Windows Update, restart rồi thử lại **một** lần.

### 1.2 Cài Docker Desktop

4. Tải **Docker Desktop for Windows** từ trang chính thức <https://www.docker.com/products/docker-desktop/>. Chạy file cài, giữ lựa chọn mặc định. Không tải từ Drive/Telegram/link lạ.
5. Mở Docker Desktop → **Settings → General** → bật **Use WSL 2 based engine** (nếu có). Sau đó **Settings → Resources → WSL Integration** → bật công tắc **Ubuntu** → **Apply & restart**.
6. Mở lại **Ubuntu**, chạy **từng lệnh một**:

   ```bash
   sudo apt update
   sudo apt install -y git
   docker version
   docker compose version
   git --version
   ```

   Kết quả đúng: `docker version` có cả **Client** và **Server**; hai lệnh sau in số phiên bản. Nếu trong Ubuntu không có `docker`, quay lại bước 5 kiểm WSL Integration.

### 1.3 Chạy đúng bốn lệnh CVAT của lớp (trong cửa sổ Ubuntu)

Lệnh dưới clone vào thư mục home của Ubuntu (`~/cvat-day2`), **không** clone vào repo bài nộp.

```bash
cd ~
git clone --depth 1 --branch v2.74.1 https://github.com/cvat-ai/cvat.git cvat-day2
cd cvat-day2
docker compose pull
docker compose up -d
```

Lần đầu tải nhiều image (vài GB), hãy chờ lệnh chạy xong. Kết quả đúng: nhiều dòng `Container ... Started/Running`.

### 1.4 Health check và tạo tài khoản

```bash
docker compose ps
docker exec -t cvat_server python manage.py health_check
```

Mọi dòng phải là `working`. Nếu có `not working`, chụp màn hình gửi mentor và **chưa** làm bước sau. Nếu tất cả `working`:

```bash
docker exec -it cvat_server bash -ic 'python3 ~/manage.py createsuperuser'
```

Nhập Username, Email, Password của bạn. Không gửi password cho ai, kể cả Claude.

Mở **Google Chrome** → `http://localhost:8080` → đăng nhập → tạo thử một task với một ảnh công khai, rồi xóa task thử đó.

### 1.5 Mở lại / dừng CVAT

```bash
cd ~/cvat-day2
docker compose start   # mở lại cho buổi làm bài (Docker Desktop phải đang chạy)
docker compose stop    # dừng sau khi đã export xong
```

**Không chạy `docker compose down -v`**: lệnh này xóa volume và làm mất task/annotation.

Khi cần hỗ trợ, gửi mentor: hệ điều hành/CPU, output `docker version`, `docker compose version`, `docker compose ps`, health check hoặc `docker compose logs --tail=200 cvat_server`. Không gửi `.env`, credential hay password.

### 1.6 Tạo task (lặp lại 9 lần)

1. Mở `http://localhost:8080`, đăng nhập.
2. Mỗi task làm theo thứ tự sau:
   1. **Tasks → `+` → Create a new task**.
   2. **Name**: gõ đúng mã task, ví dụ `easy_semantic`.
   3. **Labels → tab Raw** → xóa nội dung đang có → mở file `data/.../<task>/cvat-labels.json` trong VS Code/Notepad → `Ctrl+A`, `Ctrl+C` → dán vào ô Raw → **Done**. Kiểm số label:
      - easy: 5 · medium/cp1/cp2/cp5: 6 · hard: 12 · cp3: 4 (`traffic sign` có **dấu cách**) · cp4: 2 · cp6: 7.
   4. **Select files → My computer** → chọn **đúng** các ảnh `.jpg` trong `data/tiers/<task>/images/` hoặc `data/checkpoints/<task>/images/`. Không trộn ảnh của task khác.
   5. **Submit & Open**. Vào **Jobs** → bấm job `#...` để mở trình vẽ.

> Ảnh trong `docs/images/` chỉ để tìm nút; ảnh chấm là ảnh trong `data/`.

---

## 2. Medium: tự vẽ object đầu tiên TRƯỚC khi xem gợi ý (bắt buộc theo RULES)

**Không mở `preannotations/preview/medium_instance/` hay file JSON gợi ý của Medium trước bước này.**

1. Mở job `medium_instance`, chọn ảnh đầu tiên.
2. Thanh công cụ bên trái → **Draw new masks** (biểu tượng cọ) → chọn label, ví dụ `person` → **Shape** → dùng **Brush** (chỉnh cỡ cọ) hoặc **Polygon** bên trong công cụ mask để tô **phần nhìn thấy** của một vật. Dùng **Eraser** để xóa phần tràn. Nhấn **N** hoặc nút ✓ **Done** để kết thúc object.
3. **Save** (`Ctrl+S`).
4. Ghi ngay vào ghi chép: *tên ảnh, vị trí (ví dụ "người áo đỏ bên trái, giữa ảnh"), class, quy tắc chọn biên* (ví dụ "dừng mask ở mép giày, không lấy bóng đổ; túi xách đeo trên người thì gộp vào person"). Đây là **mục 2 của report**.
5. Export object tự vẽ để giữ lại: Menu job (☰ góc trên trái) → **Export job dataset** → **COCO 1.0** → *Save images* **tắt** → OK. Tải file về, đổi tên thành `medium_manual.zip`, đặt vào thư mục repo (file `*.zip` ở gốc repo đã bị `.gitignore` bỏ qua).
6. Chạy lệnh trộn: giữ nguyên object tự vẽ và chỉ thêm gợi ý **không trùng** với nó (cần môi trường Python, xem mục 9):

   ```powershell
   ..\.venv-day3\Scripts\python.exe tools\preannotate.py --task medium_instance --merge-with medium_manual.zip --preview
   ```

   Lệnh tạo `preannotations/medium_instance_merged.json`. Upload file này theo **bước 3**. Upload **thay toàn bộ** annotation của job, nên phải dùng bản `_merged` để không mất object tự vẽ.

---

## 3. Upload gợi ý vào job

1. Trong job: Menu ☰ → **Upload annotations**.
2. **Import format**: `COCO 1.0`. Chọn file `preannotations/<task>.json` (Medium dùng `_merged`).
3. Nếu CVAT hỏi có ghi đè annotation hiện tại không, chọn **có** (chỉ khi bạn đã dùng đúng file theo hướng dẫn).
4. Sau khi import, mở bảng **Objects** bên phải để xem số object và class. Mỗi object là một **mask**.

Gợi ý **chưa phải** đáp án. Lỗi thường gặp của máy và cách kiểm:

| Lỗi máy hay mắc | Kiểm ở đâu | Cách sửa trong CVAT |
| --- | --- | --- |
| Mask ăn sang bóng đổ / nền | Biên dưới xe, chân người | Chọn object → chuột phải → **Edit** (hoặc double-click) → Eraser → **N** |
| Gộp hai vật sát nhau thành 1 | Xe đỗ liền nhau (`cp2_slice`) | Xóa mask gộp (`Del`), vẽ lại **2 object** riêng |
| Tách một vật bị che thành 2 | `cp5_occlusion` | Xóa 2 mảnh, vẽ lại **1 mask** phủ cả hai phần nhìn thấy: tô mảnh 1 rồi tô tiếp mảnh 2 **trước khi** nhấn Done |
| Khoét kính / khe ra khỏi xe | `cp1_holes` | Edit → Brush tô lấp kính/khe vào mask xe |
| Bỏ sót vật nhỏ, xa, bị che | Mọi ảnh instance/hard | Vẽ thêm bằng Brush/Polygon |
| Sai class (truck ↔ car, bus ↔ truck) | Bảng Objects | Đổi label ngay trong bảng Objects |
| Road ↔ sidewalk theo màu | `easy_semantic`, `cp4_curb` | Ranh theo **bó vỉa/chức năng**: Edit → Eraser/Brush dọc mép bó vỉa |
| Cột/biển mảnh bị dày hoặc mất | `cp3_thin` | Zoom to, Brush 2–3 px |
| Vùng trống chưa phủ | `cp6_coverage`, `easy_semantic`, `hard` | Tô thêm vùng thuộc class của task; vùng không thuộc class nào thì để trống |
| Class thừa không có trong task | — | Script chỉ xuất class có trong `classes.json` của task |

**Khi nào có thể không dùng gợi ý:** nếu gợi ý quá tệ ở ảnh nào, xóa hết rồi vẽ tay. Ghi lại vào report.

---

## 4. Ghi chú riêng từng task

### `easy_semantic` (Segmentation mask 1.1)
- Năm class: `road`, `sidewalk`, `building`, `vegetation`, `sky`. Không có class cho xe/người/cột, nên những vùng đó **để trống**.
- Các mask chồng nhau thì mask nằm trên cùng (z-order) thắng khi export. Kiểm ranh road–sidewalk kỹ nhất.

### `medium_instance` (COCO 1.0)
- Sáu class: `person`, `bicycle`, `car`, `motorcycle`, `bus`, `truck`. **Mỗi vật một object**.
- Người ngồi trên xe máy: `person` và `motorcycle` là 2 object riêng.
- Đếm số vật thật trong ảnh và so với số object trong bảng Objects.

### `hard_panoptic` (COCO 1.0)
- 12 class. Stuff (`road`, `sidewalk`, `building`, `vegetation`, `sky`): mỗi loại một mask/ảnh. Thing: **từng** vật một mask.
- Stuff không được phủ lên thing: script đã trừ phần thing khỏi stuff. Khi bạn sửa, giữ nguyên nguyên tắc đó.
- `traffic light` là thing: từng đèn một object.

### Checkpoints
- `cp1_holes`: kính/khe **nằm trong** mask xe.
- `cp2_slice`: hai xe sát nhau là **2 object**.
- `cp5_occlusion`: vật bị cột/vật khác che là **1 object**, kể cả khi hai mảnh nhìn thấy rời nhau.
- `cp3_thin`: `pole`, `traffic sign`, `sky`, `road`. Zoom và dùng cọ nhỏ.
- `cp4_curb`: chỉ `road`, `sidewalk`. Chọn ranh theo bó vỉa.
- `cp6_coverage`: 7 class. Kiểm khe trống lớn.

---

## 5. Tự QC trước khi export (mỗi job)

1. Đúng ảnh, đúng loại segmentation.
2. Tên class khớp `classes.json`.
3. Vật thiếu / thừa / gộp / tách.
4. Biên: không tràn bóng/nền, không bỏ sót vùng rõ.
5. **Save** → chuyển sang ảnh khác → quay lại kiểm dữ liệu vẫn còn.

---

## 6. Export và đặt tên ZIP

1. Menu ☰ của job → **Export job dataset**.
2. Format: semantic → **Segmentation mask 1.1**; instance/panoptic → **COCO 1.0**. Tắt **Save images**.
3. CVAT v2.74 chuẩn bị file export trong nền. Vào **Requests** (thanh trên cùng), chờ trạng thái xong rồi bấm **Download**. File về thư mục Downloads của Windows.
4. Đổi tên **file ZIP bên ngoài** thành `<mã_task>.zip`, ví dụ `easy_semantic.zip`, rồi chép vào `submissions/`. **Không** giải nén và không sửa gì bên trong.

---

## 7. Kiểm ZIP

```powershell
..\.venv-day3\Scripts\python.exe scripts\inspect_submissions.py --dir submissions
```

`OK` chỉ có nghĩa là đúng cấu trúc. `LỖI`: quay lại CVAT, sửa, Save, export lại.

---

## 8. Điền report và nộp

1. Report: `report/individual/2A202603084_NguyenAnhThu.md`. Điền **từ ghi chép thật** của bạn:
   - Mục 1: tên ZIP và số ảnh đã làm từng task.
   - Mục 2: object Medium tự vẽ đầu tiên (bước 2), rồi một gợi ý YOLO bạn đã **sửa hoặc giữ** và lý do.
   - Mục 3: một lỗi thật bạn đã sửa (thường là lỗi của gợi ý máy, ví dụ hai xe bị gộp, bóng bị tính vào xe, road/sidewalk lệch bó vỉa). Ghi đã Save và export lại.
   - Mục 4: ba vùng bạn phân vân.
   - Dòng "Công cụ đã dùng": `CVAT local v2.74.1 (Brush/Polygon/Eraser); gợi ý tự động YOLO11x-seg (things) + SegFormer-B2 Cityscapes (stuff) qua tools/preannotate.py, đã tự kiểm/sửa`.
2. Khi đủ ZIP và report, báo Claude để commit và push, hoặc tự chạy:

   ```powershell
   git add submissions/*.zip report/individual/2A202603084_NguyenAnhThu.md
   git commit -m "Day03: submit CVAT exports and report"
   git push origin main
   ```

3. Mở lại repo trên GitHub. Xem tab **Actions → Day 3 self-check → Summary**.
4. Dán link `https://github.com/26aithuna-bot/K5-L2A-DAY03-NguyenAnhThu-2A202603084-Image-Segmentation` lên LMS **trước 12:00 ngày 12/11/2026**.

---

## 9. Môi trường Python cho gợi ý (đã cài sẵn trên máy này)

Môi trường nằm **ngoài repo**: `C:\Users\CUONG\Documents\AI_Lab\.venv-day3` (Python 3.11, PyTorch CPU, ultralytics, transformers).

```powershell
# chạy trong thư mục repo
..\.venv-day3\Scripts\python.exe tools\preannotate.py --all            # tạo gợi ý cho 9 task
..\.venv-day3\Scripts\python.exe tools\preannotate.py --task hard_panoptic --preview   # thêm ảnh overlay để xem
```

- Lần chạy đầu sẽ tự tải trọng số `yolo11x-seg.pt` (~120 MB) và SegFormer (~110 MB).
- `--conf 0.25` cho nhiều gợi ý hơn (nhiều nhiễu hơn); `--conf 0.5` cho ít hơn.
- Mô hình Cityscapes được huấn luyện trên ảnh đường phố, nên với ảnh COCO (Medium/Hard) phần stuff có thể kém. Luôn kiểm bằng mắt.
