# Tài Liệu Bàn Giao Hệ Thống - Auth API & Authentication

Tài liệu này cung cấp toàn bộ thông tin chi tiết về cơ chế xác thực JWT, phân quyền người dùng và các API Auth thuộc dự án **Smart-AI-Search-Recommendation-Assistant**.

---

## 1. Tổng Quan về Hệ Thống Xác Thực

Hệ thống sử dụng cơ chế xác thực dựa trên mã thông báo **JWT (JSON Web Token)** với chữ ký bảo mật HS256. 
* **Thời gian hết hạn của Access Token**: Mặc định là 1 ngày (1440 phút).
* **Phân quyền người dùng**: Hệ thống chia làm 2 nhóm quyền chính là `user` (người dùng thông thường) và `admin` (quản trị viên truy cập trang quản trị và dashboard).

### Quy trình Xác thực Token:
```
[Client] ──► Gửi Header "Authorization: Bearer <token>" ──► [FastAPI Middleware]
                                                                     │
                                                                     ▼
[Client] ◄── Trả về dữ liệu/Cho phép đi tiếp ◄── [get_current_user_dep] verify hợp lệ
```

---

## 2. Cấu Trúc Mã Nguồn

Toàn bộ module Auth và API xác thực được tổ chức trong thư mục [backend/app/auth/](file:///Users/tranvangiaban/Code/DA09_Smart-AI-Search-Recommendation-Assistant/backend/app/auth/) và file route API [auth.py](file:///Users/tranvangiaban/Code/DA09_Smart-AI-Search-Recommendation-Assistant/backend/app/api/routes/auth.py):

1. **`app/api/routes/auth.py`**: Định nghĩa các endpoint FastAPI (`/register`, `/login`, `/me`).
2. **`app/auth/schemas.py`**: Khai báo các Pydantic Models để ràng buộc định dạng dữ liệu Request và Response.
3. **`app/auth/dependencies.py`**: Chứa các Dependency để trích xuất token, nạp thông tin người dùng và chặn quyền truy cập (Admin check).
4. **`app/auth/security.py`**: Thực hiện logic băm mật khẩu (bcrypt) và tạo/giải mã token JWT.
5. **`app/auth/service.py`**: Chứa nghiệp vụ xử lý chính như đăng ký tài khoản mới trong database, kiểm tra đăng nhập.

---

## 3. Chi Tiết các Auth Endpoints (API Specification)

Toàn bộ các endpoint đều có tiền tố `/api/auth`.

### 1. Đăng ký Tài Khoản (`POST /register`)
* **Mô tả**: Tạo tài khoản (username/password) mới và khởi tạo user profile mặc định trong cơ sở dữ liệu. Trả về token đăng nhập ngay sau khi đăng ký thành công.
* **Request Body (`RegisterRequest`)**:
  ```json
  {
    "username": "ten_dang_nhap",   // Tối thiểu 3 ký tự, duy nhất
    "password": "mat_khau_bao_mat", // Tối thiểu 6 ký tự
    "name": "Tên Hiển Thị"
  }
  ```
* **Response (nằm trong `APIResponse.data`)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "role": "user",
    "user": {
      "user_id": "...",
      "username": "ten_dang_nhap",
      "name": "Tên Hiển Thị"
      // ... Các thông tin profile bổ sung
    }
  }
  ```

### 2. Đăng Nhập (`POST /login`)
* **Mô tả**: Kiểm tra thông tin xác thực của user. Trả về token truy cập JWT cùng dữ liệu profile đầy đủ của user.
* **Request Body (`LoginRequest`)**:
  ```json
  {
    "username": "ten_dang_nhap",
    "password": "mat_khau_bao_mat"
  }
  ```
* **Response (nằm trong `APIResponse.data`)**:
  Giống như cấu trúc phản hồi của API Đăng ký (`AuthData`).

### 3. Lấy thông tin tài khoản hiện tại (`GET /me`)
* **Mô tả**: Lấy thông tin đầy đủ của tài khoản đang đăng nhập.
* **Header yêu cầu**: `Authorization: Bearer <access_token>`
* **Response**:
  ```json
  {
    "account": {
      "id": "...",
      "username": "ten_dang_nhap",
      "role": "user"
    },
    "user_profile": {
      "name": "Tên Hiển Thị",
      "trip_types": {},
      "hotel_types": {},
      "preference_habits": {}
      // ... Các trường sở thích cá nhân hóa
    }
  }
  ```

---

## 4. Cơ Chế Phân Quyền & Bảo Vệ API (Dependencies)

Để bảo vệ các API quan trọng không cho phép người dùng ẩn danh hoặc không đủ thẩm quyền truy cập, hệ thống cung cấp 2 FastAPI Dependencies tại `app/auth/dependencies.py`:

### 🔑 `get_current_user_dep`
* **Cách dùng**: Thêm vào khai báo hàm API:
  ```python
  @router.get("/secure-data")
  async def get_data(current_user: dict = Depends(get_current_user_dep)):
  ```
* **Hoạt động**: Tự động giải mã token lấy từ Header `Authorization`. Nếu token lỗi, hết hạn hoặc không tồn tại, API sẽ tự động từ chối bằng mã lỗi **`401 Unauthorized`**.

### 🛡️ `require_admin`
* **Cách dùng**: Bảo vệ các API dành riêng cho quản trị viên (như dashboard, quản trị hệ thống):
  ```python
  @router.get("/admin-panel")
  async def admin_only(admin_user: dict = Depends(require_admin)):
  ```
* **Hoạt động**: Chạy sau khi xác thực token qua `get_current_user_dep` để lấy ra profile. Nếu vai trò (`role`) của tài khoản không phải là `'admin'`, API sẽ từ chối bằng mã lỗi **`403 Forbidden`**.
