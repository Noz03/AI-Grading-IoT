# AI-Grading-IoT

## Authentication & Authorization (Module 1)

Configure `DATABASE_URL` and a random `JWT_SECRET_KEY` of at least 32 bytes in `.env`.
`JWT_ACCESS_TOKEN_EXPIRE_SECONDS` defaults to `1800`. Authentication is available at
`POST /api/v1/auth/register`, `POST /api/v1/auth/login` and `GET /api/v1/auth/me`.
Swagger UI uses HTTP Bearer authorization. Admin-only user management is at
`/api/v1/users`.

To create the initial admin, set `SEED_ADMIN_EMAIL`, `SEED_ADMIN_FULL_NAME`, and
`SEED_ADMIN_PASSWORD` (at least 6 characters), then run:

```bash
uv run python -m ai_grading_iot.scripts.seed_admin
```

The seed command is idempotent and does not update an existing admin's password.
Run tests with `uv run pytest -v`; PostgreSQL must be running for integration tests.

Backend service cho hệ thống AI chấm bài thực hành IoT.

Tài liệu này hướng dẫn thiết lập môi trường phát triển bằng **uv**, cài đặt các dependency cần thiết, chạy FastAPI server và kiểm tra test suite trên cả **Windows** và **Linux**.

Mục tiêu của tài liệu là đảm bảo các thành viên trong nhóm có thể thiết lập môi trường giống nhau và xác nhận source code hiện tại hoạt động trước khi tiếp tục phát triển.

---

## 1. Yêu cầu môi trường

### 1.1. Hệ điều hành

Dự án hỗ trợ:

* Windows 10/11
* Linux

Các lệnh trong tài liệu được viết cho:

* **Linux:** Bash / Terminal
* **Windows:** PowerShell

---

## 2. Kiểm tra Git

Nếu project được clone từ Git repository, cần cài Git trước.

Kiểm tra Git:

### Linux

```bash
git --version
```

### Windows PowerShell

```powershell
git --version
```

Nếu Git đã được cài đặt, terminal sẽ hiển thị phiên bản Git.

---

# 3. Cài đặt uv

`uv` được sử dụng để quản lý Python version, virtual environment và dependency của project.

## 3.1. Linux

Mở Terminal và chạy:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Sau khi cài đặt, khởi động lại Terminal hoặc reload shell.

Kiểm tra:

```bash
uv --version
```

Nếu hiển thị phiên bản `uv`, quá trình cài đặt thành công.

---

## 3.2. Windows

Mở **PowerShell** và chạy:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Sau khi cài đặt, đóng và mở lại PowerShell.

Kiểm tra:

```powershell
uv --version
```

Nếu hiển thị phiên bản `uv`, quá trình cài đặt thành công.

---

# 4. Clone project

Clone repository:

```bash
git clone <REPOSITORY_URL>
```

Di chuyển vào thư mục project:

```bash
cd AI-Grading-IoT
```

Kiểm tra cấu trúc project:

```text
AI-Grading-IoT/
├── ai_grading_iot/
│   ├── __init__.py
│   ├── main.py
│   └── schemas/
│       ├── __init__.py
│       ├── practice.py
│       ├── rubric.py
│       ├── submission.py
│       └── grading_result.py
│
├── tests/
│   ├── test_practice.py
│   ├── test_rubric.py
│   ├── test_submission.py
│   └── test_grading_result.py
│
├── pyproject.toml
├── uv.lock
└── README.md
```

> Tên hoặc số lượng file có thể thay đổi khi project tiếp tục phát triển.

---

# 5. Kiểm tra Python

Project hiện sử dụng **Python 3.13**.

Kiểm tra Python:

### Linux

```bash
python3 --version
```

### Windows

```powershell
python --version
```

Có thể sử dụng `uv` để kiểm tra Python mà không cần phụ thuộc vào Python system:

```bash
uv python list
```

---

# 6. Cài đặt Python bằng uv

Nếu máy chưa có Python 3.13 phù hợp, có thể để `uv` tự cài đặt:

### Linux / Windows

```bash
uv python install 3.13
```

Kiểm tra:

```bash
uv python list
```

Sau đó project có thể sử dụng Python 3.13 thông qua virtual environment.

---

# 7. Tạo virtual environment

Từ thư mục root của project:

```bash
uv venv
```

Lệnh này tạo thư mục:

```text
.venv/
```

Virtual environment này không cần commit lên Git.

Đảm bảo `.gitignore` có:

```gitignore
.venv/
```

---

# 8. Kích hoạt virtual environment

## 8.1. Linux

```bash
source .venv/bin/activate
```

Sau khi kích hoạt, terminal thường hiển thị:

```text
(.venv)
```

ở đầu dòng.

Kiểm tra:

```bash
python --version
```

---

## 8.2. Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

Nếu PowerShell chặn việc chạy script, có thể chạy:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Sau đó kích hoạt lại:

```powershell
.venv\Scripts\Activate.ps1
```

Kiểm tra:

```powershell
python --version
```

---

# 9. Cài đặt dependencies

Project sử dụng `pyproject.toml` và `uv.lock` để quản lý dependency.

Sau khi clone project, chạy:

```bash
uv sync
```

`uv` sẽ:

1. Đọc dependency từ `pyproject.toml`.
2. Sử dụng `uv.lock` để xác định phiên bản dependency.
3. Cài đặt các package cần thiết.
4. Đồng bộ môi trường `.venv`.

Không nên tự cài từng package bằng `pip` nếu dependency đã được khai báo trong project.

---

# 10. Kiểm tra các package

Sau khi `uv sync` hoàn tất, kiểm tra:

```bash
uv pip list
```

Các dependency chính hiện tại bao gồm:

* FastAPI
* Pydantic
* pytest
* uvicorn

Danh sách chính thức phải được lấy từ `pyproject.toml` của project.

Không cần cài lại các package này bằng `pip` nếu `uv sync` đã chạy thành công.

---

# 11. Chạy FastAPI server

Source code hiện tại sử dụng FastAPI.

Từ root project:

```bash
uv run uvicorn ai_grading_iot.main:app --reload
```

Nếu server chạy thành công, terminal sẽ hiển thị tương tự:

```text
Uvicorn running on http://127.0.0.1:8000
```

Có thể truy cập:

```text
http://127.0.0.1:8000
```

Response dự kiến:

```json
{
  "message": "AI-Grading-IoT API is running"
}
```

---

# 12. FastAPI Swagger UI

FastAPI tự động cung cấp Swagger UI.

Mở trình duyệt:

```text
http://127.0.0.1:8000/docs
```

Swagger UI cho phép kiểm tra các API hiện có mà không cần frontend.

Ngoài ra có thể truy cập:

```text
http://127.0.0.1:8000/redoc
```

để sử dụng ReDoc.

---

# 13. Chạy test

Project sử dụng `pytest`.

Không cần activate `.venv` nếu sử dụng `uv run`.

Chạy toàn bộ test:

```bash
uv run pytest
```

Nếu muốn output chi tiết hơn:

```bash
uv run pytest -v
```

Kết quả thành công sẽ có dạng:

```text
============================= test session starts =============================
...
============================== X passed in Xs ================================
```

Trong đó `X` là tổng số test hiện tại của project.

---

# 14. Chạy test theo từng schema

Có thể chạy test riêng cho từng module.

Ví dụ:

### Practice

```bash
uv run pytest tests/test_practice.py -v
```

### Rubric

```bash
uv run pytest tests/test_rubric.py -v
```

### Submission

```bash
uv run pytest tests/test_submission.py -v
```

### GradingResult

```bash
uv run pytest tests/test_grading_result.py -v
```

Nếu project chưa có một trong các file test trên thì bỏ qua file tương ứng.

---

# 15. Kiểm tra source code bằng pytest

Trước khi tiếp tục phát triển, mỗi thành viên cần chạy:

```bash
uv sync
```

sau đó:

```bash
uv run pytest -v
```

Toàn bộ test phải pass.

Ví dụ:

```text
============================= test session starts =============================

collected XX items

tests/test_practice.py ........
tests/test_rubric.py ........
tests/test_submission.py .....
tests/test_grading_result.py .....

============================== XX passed in Xs ================================
```

Nếu test fail, cần xử lý lỗi trước khi tiếp tục phát triển feature mới.

---

# 16. Kiểm tra API thủ công

Sau khi chạy:

```bash
uv run uvicorn ai_grading_iot.main:app --reload
```

mở:

```text
http://127.0.0.1:8000/docs
```

Kiểm tra các endpoint hiện có.

Có thể sử dụng Swagger UI để gửi request trực tiếp.

Ví dụ:

```text
GET /
```

Expected response:

```json
{
  "message": "AI-Grading-IoT API is running"
}
```

---

# 17. Quy trình setup trên máy mới

Thành viên mới có thể thực hiện theo thứ tự sau.

## Linux

```bash
git clone <REPOSITORY_URL>
cd AI-Grading-IoT

uv --version

uv python install 3.13

uv venv

source .venv/bin/activate

uv sync

uv run pytest -v

uv run uvicorn ai_grading_iot.main:app --reload
```

Sau đó mở:

```text
http://127.0.0.1:8000/docs
```

---

## Windows PowerShell

```powershell
git clone <REPOSITORY_URL>
cd AI-Grading-IoT

uv --version

uv python install 3.13

uv venv

.venv\Scripts\Activate.ps1

uv sync

uv run pytest -v

uv run uvicorn ai_grading_iot.main:app --reload
```

Sau đó mở:

```text
http://127.0.0.1:8000/docs
```

---

# 18. Quy tắc làm việc với dependency

Không nên thực hiện:

```bash
pip install fastapi
pip install pytest
```

nếu package đã được khai báo trong project.

Thay vào đó, sử dụng:

```bash
uv add <package>
```

Ví dụ:

```bash
uv add httpx
```

Sau khi thêm package, `uv` sẽ cập nhật:

```text
pyproject.toml
uv.lock
```

Hai file này cần được commit lên Git.

Sau đó thành viên còn lại chỉ cần:

```bash
uv sync
```

để đồng bộ môi trường.

---

# 19. Khi pull code mới

Mỗi khi pull code từ Git repository:

```bash
git pull
```

nên chạy:

```bash
uv sync
```

Sau đó chạy:

```bash
uv run pytest -v
```

Nếu test pass mới tiếp tục phát triển.

---

# 20. Quy tắc Git đối với môi trường Python

Không commit:

```text
.venv/
__pycache__/
.pytest_cache/
```

Ví dụ `.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]

# Virtual environment
.venv/
venv/

# Pytest
.pytest_cache/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

Các file quan trọng cần commit:

```text
pyproject.toml
uv.lock
```

`uv.lock` đặc biệt quan trọng vì giúp các thành viên sử dụng cùng phiên bản dependency.

---

# 21. Checklist trước khi tiếp tục phát triển

Mỗi thành viên cần xác nhận:

### Environment

* [ ] Git đã được cài đặt.
* [ ] `uv --version` hoạt động.
* [ ] Python 3.13 đã được cài đặt.
* [ ] `.venv` được tạo thành công.
* [ ] `uv sync` chạy thành công.

### Source code

* [ ] Source code clone/pull thành công.
* [ ] Không có lỗi import.
* [ ] `uv run pytest -v` chạy thành công.
* [ ] Tất cả test hiện tại đều PASS.

### FastAPI

* [ ] FastAPI server khởi động thành công.
* [ ] `http://127.0.0.1:8000` hoạt động.
* [ ] `/docs` mở được.
* [ ] Các API hiện tại có thể test bằng Swagger UI.

---

# 22. Quy trình phát triển hằng ngày

Quy trình đề xuất:

```text
Pull latest code
      │
      ▼
   uv sync
      │
      ▼
  Run tests
      │
      ▼
  Develop feature
      │
      ▼
  Write/update tests
      │
      ▼
  Run tests again
      │
      ▼
Commit changes
      │
      ▼
Push to repository
```

Các lệnh thường dùng:

```bash
git pull

uv sync

uv run pytest -v

uv run uvicorn ai_grading_iot.main:app --reload
```

---

# 23. Các lệnh uv quan trọng

| Lệnh                     | Mục đích                              |
| ------------------------ | ------------------------------------- |
| `uv --version`           | Kiểm tra uv                           |
| `uv python list`         | Xem Python versions                   |
| `uv python install 3.13` | Cài Python 3.13                       |
| `uv venv`                | Tạo virtual environment               |
| `uv sync`                | Đồng bộ dependencies                  |
| `uv add <package>`       | Thêm dependency                       |
| `uv remove <package>`    | Xóa dependency                        |
| `uv pip list`            | Xem packages                          |
| `uv run <command>`       | Chạy command trong môi trường project |

---

# 24. Các lệnh project thường dùng

### Chạy test

```bash
uv run pytest -v
```

### Chạy FastAPI

```bash
uv run uvicorn ai_grading_iot.main:app --reload
```

### Kiểm tra API

```text
http://127.0.0.1:8000
```

### Swagger

```text
http://127.0.0.1:8000/docs
```

### ReDoc

```text
http://127.0.0.1:8000/redoc
```

---

# 25. Kết luận

Trước khi tiếp tục phát triển các module tiếp theo của AI-Grading-IoT, cả hai thành viên cần đảm bảo rằng:

1. Cùng sử dụng `uv` để quản lý Python environment.
2. Cùng sử dụng Python 3.13.
3. Dependencies được quản lý thông qua `pyproject.toml` và `uv.lock`.
4. Không commit `.venv`.
5. `uv sync` chạy thành công.
6. Toàn bộ test hiện tại đều PASS.
7. FastAPI server khởi động thành công.
8. Swagger UI tại `/docs` hoạt động bình thường.

Khi hai máy đều đạt các điều kiện trên, môi trường phát triển được xem là đã sẵn sàng để tiếp tục triển khai các chức năng tiếp theo của hệ thống.

## Module 2 — Course và Practice API

Tất cả endpoint dưới đây dùng tiền tố `/api/v1` và yêu cầu header
`Authorization: Bearer <access_token>` lấy từ `POST /api/v1/auth/login`.
Admin quản lý mọi Course; Teacher chỉ quản lý Practice của Course được phân công;
Student chỉ thấy Practice đã xuất bản trong Course đang theo học.

| Method | Path | Quyền | Chức năng |
|---|---|---|---|
| POST | `/courses` | Admin | Tạo Course; code được trim và chuyển chữ hoa |
| GET | `/courses` | Admin | Danh sách Course, `limit`/`offset` |
| GET | `/courses/my` | Teacher, Student | Course được phân công hoặc đang theo học |
| GET | `/courses/{course_id}` | Thành viên Course, Admin | Chi tiết Course |
| PATCH | `/courses/{course_id}` | Admin | Sửa tên, mô tả |
| DELETE | `/courses/{course_id}` | Admin | Xóa Course chưa có Practice |
| POST | `/courses/{course_id}/teachers` | Admin | Phân công Teacher |
| GET | `/courses/{course_id}/teachers` | Admin, Teacher của Course | Danh sách Teacher |
| DELETE | `/courses/{course_id}/teachers/{teacher_id}` | Admin | Gỡ Teacher |
| POST | `/courses/join` | Student | Tham gia bằng Course code |
| POST | `/courses/{course_id}/students` | Admin | Ghi danh Student |
| GET | `/courses/{course_id}/students` | Admin, Teacher của Course | Danh sách Student |
| DELETE | `/courses/{course_id}/students/{student_id}` | Admin | Hủy ghi danh, giữ lịch sử bài nộp |
| POST | `/courses/{course_id}/practices` | Admin, Teacher của Course | Tạo Practice dạng Draft |
| GET | `/courses/{course_id}/practices` | Thành viên Course, Admin | Danh sách; Student chỉ thấy Published |
| GET | `/practices/{practice_id}` | Theo quyền Course và trạng thái | Chi tiết Practice |
| PATCH | `/practices/{practice_id}` | Admin, Teacher của Course | Sửa từng phần nội dung được phép |
| POST | `/practices/{practice_id}/publish` | Admin, Teacher của Course | Chuyển Draft sang Published |
| POST | `/practices/{practice_id}/archive` | Admin, Teacher của Course | Chuyển Published sang Archived |
| DELETE | `/practices/{practice_id}` | Admin, Teacher của Course | Xóa nếu chưa có Submission |

Ví dụ:

```bash
curl -X POST http://localhost:8000/api/v1/courses \
  -H 'Authorization: Bearer <admin_token>' -H 'Content-Type: application/json' \
  -d '{"code":" IOT101 ","name":"Internet of Things"}'

curl -X POST http://localhost:8000/api/v1/courses/join \
  -H 'Authorization: Bearer <student_token>' -H 'Content-Type: application/json' \
  -d '{"course_code":" iot101 "}'
```

`PATCH /practices/{practice_id}` chỉ nhận `title`, `description`, `requirements`,
`environment`, `hardware`, `version`. Practice có Submission không được sửa nội dung;
Published chưa có Submission chỉ sửa được `title` và `description`. Xuất bản yêu cầu
đủ Code, Data, Vision Rubric thuộc Practice, tham chiếu ID hợp lệ và tổng trọng số
100%. Module 3 bên dưới bổ sung tạo và chỉnh sửa Rubric bằng AI.

## Module 3 — Rubric Management và AI Generation

Khi tạo Practice, backend commit Practice ở trạng thái `draft` trước, sau đó gọi Groq
để đề xuất một Rubric `code`, `data` và `vision`. Phản hồi tạo Practice giữ các trường
cũ và thêm `rubric_generation` với `status` (`succeeded` hoặc `failed`) và `message`.
Nếu Groq lỗi hoặc nội dung không hợp lệ, Practice vẫn tồn tại; không tạo Rubric giả.
Người dùng có thể gọi `generate` để thử lại.

Cấu hình `GROQ_API_KEY` trong môi trường; `GROQ_MODEL` là tùy chọn. Client dùng
JSON response format và timeout 30 giây. Không đưa khóa API vào request.

Các endpoint dùng tiền tố `/api/v1` và Bearer token:

| Method | Path | Quyền | Chức năng |
|---|---|---|---|
| POST | `/practices/{practice_id}/rubrics/generate` | Admin, Teacher được phân công | Sinh bộ Rubric còn thiếu; trả 409 nếu đã có Rubric |
| GET | `/practices/{practice_id}/rubrics` | Admin, Teacher được phân công; Student đã ghi danh khi Published | Liệt kê Rubric |
| GET | `/rubrics/{rubric_id}` | Như endpoint liệt kê | Chi tiết Rubric |
| PATCH | `/rubrics/{rubric_id}` | Admin, Teacher được phân công | Sửa `weight`, `criteria` của Draft |
| POST | `/practices/{practice_id}/rubrics/regenerate` | Admin, Teacher được phân công | Cố ý thay toàn bộ đề xuất |

Ví dụ sửa một Rubric:

```json
{"weight": 70, "criteria": ["Initialize LED GPIO", "Handle required errors"]}
```

Phản hồi chi tiết gồm `id`, `practice_id`, `type`, `weight` và `criteria`.
Một loại không áp dụng vẫn có Rubric với `weight: 0`, `criteria: []`.
Trọng số nằm trong 0–100, tối đa hai chữ số thập phân; loại có trọng số dương
phải có tiêu chí có nội dung. Có thể sửa một trọng số khiến tổng tạm thời khác 100
khi còn Draft. Publish chỉ thành công khi đủ ba loại, ID tham chiếu khớp, tổng
trọng số bằng 100 và tiêu chí hợp lệ. Published và Archived không cho sửa hay sinh lại.

`generate` giữ nguyên Rubric đã có; với bộ một phần, dùng `regenerate` để thay thế
theo hành động rõ ràng. `regenerate` giữ các ID hiện có và commit cả ba Rubric cùng
tham chiếu trong một transaction. Nếu Groq thất bại, các chỉnh sửa trước đó còn nguyên.
Khi yêu cầu Practice thay đổi trong lúc Groq xử lý, API trả 409 để yêu cầu thử lại.
Lỗi nhà cung cấp trả 503 với thông báo không chứa chẩn đoán nhạy cảm.

Chạy kiểm thử với PostgreSQL đang hoạt động:

```bash
uv run pytest -v
uv run alembic check
```

## Module 4 — Submission và ảnh minh chứng

Tất cả endpoint dùng tiền tố `/api/v1` và yêu cầu JWT Bearer. Student phải còn
ghi danh trong Course và Practice phải `published` để tạo, sửa hoặc nộp bài.
Admin và Teacher được phân công chỉ có quyền xem bài/ảnh; Student chỉ xem bài của
chính mình khi còn ghi danh.

| Method | Path | Quyền | Chức năng |
|---|---|---|---|
| POST | `/practices/{practice_id}/submissions` | Student | Tạo Draft; body gồm `description`, `code` tùy chọn |
| GET | `/submissions/my` | Student | Bài nộp của mình, `limit`/`offset` |
| GET | `/practices/{practice_id}/submissions` | Admin, Teacher của Course | Danh sách bài nộp |
| GET | `/submissions/{submission_id}` | Chủ bài, Admin, Teacher của Course | Chi tiết |
| PATCH | `/submissions/{submission_id}` | Chủ bài | Sửa `description` hoặc `code` |
| POST | `/submissions/{submission_id}/submit` | Chủ bài | Nộp hoặc nộp lại |
| POST | `/submissions/{submission_id}/images` | Chủ bài | Upload multipart trường `file` |
| GET | `/submissions/{submission_id}/images/{image_id}` | Chủ bài, Admin, Teacher của Course | Đọc ảnh có xác thực |
| DELETE | `/submissions/{submission_id}/images/{image_id}` | Chủ bài | Xóa ảnh |

Mỗi Student chỉ có một Submission cho mỗi Practice. Draft mới có `submitted_at=null`.
Submit yêu cầu ít nhất một trong `code`, `description` hoặc ảnh có nội dung; trạng thái
chuyển sang `submitted` và ghi thời gian UTC. Submit lặp khi chưa sửa trả 409. Khi
sửa nội dung hoặc thêm/xóa ảnh của bài đã nộp, bài trở lại `draft`, xóa thời gian nộp
và xóa GradingResult cũ trong cùng giao dịch database. Nộp lại giữ nguyên UUID và
ghi thời gian mới. Hiện chưa lưu lịch sử từng lần nộp và chưa chạy AI grading.

Ảnh JPEG, PNG, WebP được kiểm tra bằng Pillow, giới hạn 10 MiB mỗi ảnh và 5 ảnh
mỗi bài. Backend giải mã và mã hóa lại, bỏ metadata, đặt tên UUID và chỉ lưu đường
dẫn tương đối trong database. Ảnh được lưu tại `UPLOAD_DIR` (mặc định `./uploads`,
đường dẫn tương đối được tính từ thư mục gốc dự án), không được phục vụ bằng
StaticFiles. Đặt `UPLOAD_DIR` tới thư mục bền vững có quyền ghi khi triển khai.
Docker Compose hiện chỉ chạy PostgreSQL; nếu chạy backend trong container, đặt
`UPLOAD_DIR=/app/uploads` và gắn named volume hoặc bind mount bền vững vào
`/app/uploads`. Không xóa volume khi triển khai lại.

Upload ghi tệp tạm trong cùng thư mục rồi đổi tên; lỗi giao dịch sẽ rollback và
xóa tệp vừa tạo. Xóa ảnh commit tham chiếu database trước, sau đó xóa tệp vật lý;
nếu bước dọn tệp lỗi, backend ghi log và tệp mồ côi có thể được dọn sau. Không có
job dọn tệp mồ côi tự động trong MVP. Kiểm thử dùng thư mục ảnh tạm:

```bash
uv run pytest -v
uv run alembic check
```


## Module 5 — AI Grading Integration

Áp dụng migration mới trên PostgreSQL đang sử dụng, không đặt lại dữ liệu:

```bash
uv run alembic upgrade head
uv run alembic check
uv run pytest -v
```

`PATCH /api/v1/submissions/{submission_id}` nhận thêm `data_evidence`:

```json
{
  "data_evidence": {
    "measurements": [{"name": "temperature", "value": 29.5, "unit": "C"}],
    "dashboard": {"description": "ESP32 dashboard", "image_ids": []},
    "notes": "Student-provided readings"
  }
}
```

Các số đo do Student cung cấp, chưa được xác thực bằng thiết bị. Tối đa 100 số đo,
5 ảnh dashboard, 64 KiB dữ liệu JSON; tên số đo tối đa 100 ký tự, đơn vị 32,
mô tả dashboard 2.000 và ghi chú 5.000 ký tự. `image_ids` phải thuộc ảnh đã upload
cho chính Submission qua API Module 4. Xóa ảnh cũng xóa ID tương ứng khỏi evidence.
Gửi `data_evidence: null` để xóa evidence. Sửa nội dung thực sự hoặc thêm/xóa ảnh
tăng `revision`, đưa bài đã nộp về Draft và vô hiệu kết quả chấm cũ. PATCH không đổi
nội dung và Submit không tăng revision.

| Method | Path sau `/api/v1` | Quyền |
|---|---|---|
| POST | `/submissions/{submission_id}/grade` | Student chủ bài còn ghi danh, Teacher được phân công, Admin |
| POST | `/submissions/{submission_id}/regrade` | Teacher được phân công, Admin |
| GET | `/submissions/{submission_id}/grading-result` | Chủ bài còn ghi danh, Teacher được phân công, Admin |
| GET | `/grading-results/{result_id}` | Như trên, kiểm tra theo Submission sở hữu kết quả |

Submit chỉ đổi trạng thái, không gọi Groq. Grade yêu cầu bài `submitted` và chưa có
GradingResult; Regrade yêu cầu kết quả cũ và giữ nguyên ID. Code Grader dùng code,
Practice và Code Rubric đã lưu. Data Grader dùng Groq với tiêu chí Data Rubric,
code và evidence do Student cung cấp. Client hiện chỉ gửi văn bản; Data Grader không
xem nội dung ảnh dashboard. Tiêu chí cần kiểm tra hình ảnh hoặc evidence còn thiếu
được đánh dấu `insufficient`, `data_score=null`.

Trọng số Code, Data, Vision phải đủ 100. Chỉ gọi grader cho thành phần có trọng số
dương. `vision_score` luôn null trong Module 5. `final_score` chỉ tính khi mọi thành
phần có trọng số dương đều có điểm; phép tính dùng Decimal và làm tròn 2 chữ số.
Kết quả thiếu điểm có trạng thái `partial` hoặc `insufficient_evidence`. Không chuyển
điểm thiếu thành 0. Có thể đặt `GRADING_TIMEOUT_SECONDS` (mặc định 60) cùng
`GROQ_API_KEY` và `GROQ_MODEL` hiện có. Provider lỗi trả 502 và không ghi kết quả;
Regrade lỗi giữ nguyên kết quả cũ. Service kết thúc giao dịch đọc trước khi gọi Groq,
sau đó khóa và kiểm tra lại revision, Practice và Rubric trước khi lưu. Các lời gọi
Groq đồng thời trên nhiều worker vẫn có thể trùng; ràng buộc unique và khóa hàng
ngăn kết quả lưu trùng. Chưa có Vision Grader, queue hay lịch sử lần chấm.
## Module 6 — Vision Grader (backend)

Vision Grading dùng luồng `Router → VisionGradingService → repositories / YOLOInferenceService / VisionGrader → PostgreSQL / storage / Groq`. Cài runtime YOLO bằng `uv sync --extra vision`; đặt trọng số đã fine-tune tại `models/yolo11_iot/best.pt` hoặc cấu hình `YOLO_MODEL_PATH`. File `.pt` không được commit. Model được tải lười một lần mỗi worker; thiếu hoặc lỗi trọng số chỉ làm endpoint Vision trả 503, các API khác vẫn hoạt động. `YOLO_DEVICE` nhận thiết bị Ultralytics hỗ trợ như `cpu` hoặc CUDA, `YOLO_CONFIDENCE` và `YOLO_IOU_THRESHOLD` đặt ngưỡng, `VISION_MAX_CONCURRENT_INFERENCES` giới hạn inference. Với máy chỉ có CPU, cần cài bản PyTorch CPU tương thích trước khi cài extra Vision để tránh tải các gói CUDA không cần thiết.

Đặt `GROQ_API_KEY` và `VISION_GROQ_MODEL` là ID Qwen vision-capable mà tài khoản Groq thực sự truy cập được; không có model mặc định chưa xác minh. `VISION_GROQ_TIMEOUT_SECONDS` giới hạn thời gian mỗi lời gọi. Trước khi bật production, kiểm tra với tài khoản thật rằng model nhận hai ảnh dạng `image_url` data URI PNG trong một chat completion, trả JSON object, và đáp ứng giới hạn kích thước/rate limit. Test tự động chỉ giả lập Groq; chúng không chứng minh quyền truy cập model thật.

Mỗi Submission dùng toàn bộ ảnh kit trong `Submission.images` theo thứ tự, tối đa năm ảnh. YOLO nhận ảnh gốc và tạo Detection JSON gồm `image_id`, kích thước gốc, `model_version`, từng `class_id`, tên class đọc từ weights, confidence và bbox `xyxy` pixel. Từ JSON này hệ thống vẽ hộp, nhãn và độ tin cậy trên ảnh PNG mới; ảnh gốc không thay đổi. Mỗi ảnh tạo một yêu cầu Qwen chứa đúng hai ảnh thị giác (gốc và đã chú thích), detections, yêu cầu Practice và Vision Rubric. Một yêu cầu text cuối kết hợp toàn bộ quan sát thành **một** Vision Score; không lấy trung bình điểm từng ảnh. Trạng thái `insufficient` lưu `vision_score=null` và phản hồi lý do. Detector không xác nhận được mạch hoạt động, kết nối điện ẩn, dây khuất hay số đo đúng; detection bị thiếu cũng không chứng minh linh kiện vắng mặt. Điểm tổng chỉ tính khi mọi thành phần có trọng số dương đều có điểm.

Các API dùng JWT và quyền Course/Submission: Admin và Teacher được phân công có thể grade/regrade; Student là chủ bài đang ghi danh chỉ được grade lần đầu và đọc kết quả/artifact. Chỉ bài `submitted` được chấm. API:

| Method | Endpoint | Công dụng |
|---|---|---|
| POST | `/api/v1/submissions/{submission_id}/grade-vision` | Chấm Vision lần đầu |
| POST | `/api/v1/submissions/{submission_id}/regrade-vision` | Chấm lại Vision |
| GET | `/api/v1/submissions/{submission_id}/vision-result` | Xem điểm và đánh giá |
| GET | `/api/v1/submissions/{submission_id}/vision-detections` | Xem Detection JSON |
| GET | `/api/v1/submissions/{submission_id}/vision-artifacts/{image_id}` | Xem PNG đã chú thích |

`vision_evaluation` được lưu JSONB bằng migration Module 6, tách khỏi `code_evaluation` và `data_evaluation`. Ảnh chú thích nằm trong `UPLOAD_DIR/grading_artifacts/<submission>/<revision>/<run>/`, chỉ đọc qua API có quyền. Dịch vụ kiểm tra revision và Rubric trước khi commit, khóa Submission khi ghi, gộp điểm vào bản GradingResult mới nhất, và xóa artifact mới khi ghi DB thất bại. Regrade lỗi kỹ thuật giữ nguyên kết quả cũ. Vision có thể mất nhiều thời gian do tối đa năm yêu cầu đa phương thức và một yêu cầu tổng hợp; chưa có background queue.

Chạy `uv run alembic upgrade head`, `uv run alembic check`, `uv run pytest -v`. Test thường dùng mock YOLO/Groq, không cần weights/GPU/khóa API. Sau khi nhận `best.pt`, thực hiện thử riêng với ảnh kit thật: xác minh phiên bản Ultralytics, class IDs/tên class, độ phân giải, confidence, bbox gốc, CPU/GPU, annotations và serialization. Tiếp đó thử Groq live có chọn lọc với hai ảnh trong một yêu cầu và yêu cầu tổng hợp, kiểm tra model ID/quota/timeout. Inference trên weights thật và Groq live chưa được xác minh chỉ bằng test mock.
