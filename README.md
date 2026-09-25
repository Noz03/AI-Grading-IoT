# AI-Grading-IoT

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

