# Hướng dẫn Host Dự án hoàn thiện (Full-stack Hosting)

Khi dự án Income Verification Expert đã code xong 100% (cả Frontend và Backend), để cung cấp một trải nghiệm "click vào link là sử dụng được", bạn nên sử dụng kiến trúc **Tách biệt Frontend - Backend (Decoupled Hosting)**. Đây là kiến trúc đám mây miễn phí và xịn nhất hiện nay cho các dự án demo/hackathon.

Hệ thống sẽ được chia thành 3 phần:

## 1. Cơ sở dữ liệu (Database) - Supabase / Neon
- **Nhiệm vụ:** Lưu trữ toàn bộ dữ liệu hồ sơ (CaseContext), Audit Logs và dữ liệu vector RAG (pgvector).
- **Cách làm:**
  1. Truy cập [Supabase.com](https://supabase.com) hoặc [Neon.tech](https://neon.tech), tạo tài khoản miễn phí.
  2. Tạo một Project mới.
  3. Lấy chuỗi kết nối Database URL. (Nó sẽ có định dạng `postgresql://user:pass@host:5432/db_name`).
  4. Bạn không cần phải setup gì thêm, cơ sở dữ liệu đã sẵn sàng trên Cloud.

## 2. API & AI Logic (Backend) - Render / Railway
- **Nhiệm vụ:** Chạy FastAPI, gọi AI Model (Qwen, GLM), xử lý nghiệp vụ.
- **Cách làm:**
  1. Vào thư mục `backend/` trong repo này, đảm bảo bạn đã điền các file cấu hình như `render.yaml` và `Dockerfile`.
  2. Truy cập [Render.com](https://render.com), đăng nhập bằng GitHub.
  3. Chọn **New** > **Blueprint** > Chọn repo của bạn.
  4. Render sẽ tự động đọc file cấu hình và tiến hành build (khoảng 3-5 phút).
  5. Trong màn hình Dashboard của Render, vào mục **Environment**, thêm biến `DATABASE_URL` và paste cái chuỗi kết nối lấy ở Bước 1 vào.
  6. Kết quả: Bạn sẽ có một link API chạy ngầm, ví dụ: `https://api-income-expert.onrender.com`.

## 3. Giao diện (Frontend) - Vercel
- **Nhiệm vụ:** Hiển thị giao diện UI đẹp mắt cho Giám khảo (viết bằng Next.js).
- **Cách làm:**
  1. Đẩy code giao diện lên thư mục `frontend/` trên GitHub.
  2. Truy cập [Vercel.com](https://vercel.com), đăng nhập bằng GitHub.
  3. Chọn **Add New...** > **Project** > Chọn repo của bạn.
  4. Tại phần **Root Directory**, ấn Edit và chọn thư mục `frontend`.
  5. Mở phần **Environment Variables**, thêm một biến mới:
     - Tên: `NEXT_PUBLIC_API_URL`
     - Giá trị: `https://api-income-expert.onrender.com` (Link lấy ở bước 2).
  6. Ấn **Deploy**.
  7. Kết quả: Sau 1 phút, Vercel sẽ cấp cho bạn một link duy nhất siêu mượt (Ví dụ: `https://income-expert.vercel.app`).

---

## 🚀 Trải nghiệm người dùng cuối (End-User Flow)
1. Giám khảo click vào link **Vercel** duy nhất.
2. Trình duyệt tải ngay lập tức giao diện UI bóng bẩy (Không hề biết có sự tồn tại của Render hay Supabase).
3. Khi Giám khảo bấm "Bắt đầu xác minh", Vercel âm thầm gửi request sang API **Render**.
4. **Render** xử lý dữ liệu, bóc tách OCR, gọi AI Agents, và lưu dấu vết kiểm toán xuống **Supabase**.
5. Giao diện Vercel nhận lại kết quả từ Render và hiển thị báo cáo ra màn hình trong tích tắc.

Ưu điểm của mô hình này: **Miễn phí 100%**, tự động cập nhật code mỗi khi bạn ấn `git push` (CI/CD Auto Deploy), và tốc độ truy cập cực kỳ nhanh!
