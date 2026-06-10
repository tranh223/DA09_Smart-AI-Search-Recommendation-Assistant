# Báo Cáo Thống Kê Dữ Liệu Tag

Báo cáo này trình bày kết quả thống kê chi tiết từ việc phân tích tệp dữ liệu SQL sau khi đã chạy chuẩn hóa và làm sạch dữ liệu, bao gồm thông tin của **520 khách sạn**, **9.364 phòng**, và **4.991 địa điểm lân cận**.

## 1. Tóm Tắt Kết Quả Thống Kê

| Trường dữ liệu | Tổng số loại độc nhất (Unique) | Ghi chú |
| :--- | :---: | :--- |
| **Đối tượng phù hợp (`suitable_for`)** | **6** | Tất cả các đối tượng lưu trú chính |
| **Tiện ích khách sạn (`amenities`)** | **269** | Đã được chuẩn hóa và loại bỏ các tiện ích không cần thiết |
| **Cảnh quan phòng (`room_view`)** | **10** | Đã gộp các hướng gần nghĩa theo nhóm có số lượng lớn nhất |
| **Tiện ích phòng (`room_amenities`)** | **87** | Các tiện ích được trang bị trong phòng của khách sạn |
| **Nhãn đánh giá (`reviews_detail/tags`)** | **45** | Chỉ tính các nhãn có `mentioned > 4` tại từng khách sạn |
| **Phân loại địa điểm lân cận (`PLACE_TYPE`)** | **53** | Loại hình địa điểm xung quanh khách sạn (từ bảng `nearby_places`) |

---

## 2. Chi Tiết Đối Tượng Phù Hợp (`suitable_for` - 6 loại)

Dưới đây là danh sách toàn bộ 6 loại đối tượng phù hợp cùng số lượng khách sạn đáp ứng đối tượng đó (sắp xếp giảm dần):

| STT | Đối tượng phù hợp | Số lượng khách sạn áp dụng | Tỷ lệ (%) |
| :---: | :--- | :---: | :---: |
| 1 | Khách du lịch một mình | 501 | 96.35% |
| 2 | Cặp đôi | 499 | 95.96% |
| 3 | Nhóm du khách | 499 | 95.96% |
| 4 | Gia đình có trẻ nhỏ | 489 | 94.04% |
| 5 | Khách đi công tác | 451 | 86.73% |
| 6 | Gia đình có thanh thiếu niên | 451 | 86.73% |

---

## 3. Tiện Ích Phổ Biến Nhất (`amenities` - Top 30 trên tổng số 269 loại)

Dưới đây là top 30 tiện ích phổ biến nhất xuất hiện tại 520 khách sạn (sau khi đã chạy chuẩn hóa và lọc sạch). Có thể xem danh sách đầy đủ tại tệp [amenities_statistics_clean_normalized.csv](data_csv/amenities_statistics_clean_normalized.csv).

| STT | Tên tiện ích | Số khách sạn sở hữu | Tỷ lệ (%) |
| :---: | :--- | :---: | :---: |
| 1 | WiFi miễn phí | 505 | 97.12% |
| 2 | Tiếng Anh | 474 | 91.15% |
| 3 | Bảo vệ 24 giờ | 462 | 88.85% |
| 4 | Bàn tiếp tân 24 giờ | 461 | 88.65% |
| 5 | Dịch vụ giặt là | 451 | 86.73% |
| 6 | Phòng không hút thuốc | 442 | 85.00% |
| 7 | Giữ hành lý | 431 | 82.88% |
| 8 | Thang máy | 419 | 80.58% |
| 9 | Thích hợp cho gia đình trẻ em | 409 | 78.65% |
| 10 | CCTV trong khu vực chung | 393 | 75.58% |
| 11 | Phòng gia đình | 392 | 75.38% |
| 12 | Điều hòa | 391 | 75.19% |
| 13 | Đỗ xe miễn phí | 383 | 73.65% |
| 14 | Dịch vụ ủi đồ | 365 | 70.19% |
| 15 | Điều hòa ở khu vực chung | 358 | 68.85% |
| 16 | Khu vực hút thuốc | 355 | 68.27% |
| 17 | Hoàn toàn không hút thuốc | 345 | 66.35% |
| 18 | Nhà hàng | 343 | 65.96% |
| 19 | Đưa đón sân bay | 329 | 63.27% |
| 20 | CCTV bên ngoài chỗ nghỉ | 327 | 62.88% |
| 21 | Nhận/trả phòng 24 giờ | 312 | 60.00% |
| 22 | Giặt khô | 311 | 59.81% |
| 23 | Nhận trả phòng nhanh | 303 | 58.27% |
| 24 | Quán cà phê | 297 | 57.12% |
| 25 | Dịch vụ đưa đón | 285 | 54.81% |
| 26 | Cơ sở vật chất cho họp mặt tiệc lớn | 282 | 54.23% |
| 27 | Đỗ xe tại chỗ | 281 | 54.04% |
| 28 | Bữa sáng tự chọn | 272 | 52.31% |
| 29 | Dịch vụ taxi | 271 | 52.12% |
| 30 | Nhân viên trực cửa | 258 | 49.62% |

---

## 4. Chi Tiết Cảnh Quan Phòng (`room_view` - 10 loại đã chuẩn hóa)

Thống kê phân phối cảnh quan phòng (room view) từ **9.364 phòng ngủ** sau khi gộp các nhóm có ý nghĩa giống nhau:

| STT | Loại cảnh quan (Room View) | Số lượng phòng | Tỷ lệ (%) | Ghi chú / Các nhãn đã được gộp nhóm |
| :---: | :--- | :---: | :---: | :--- |
| 1 | không có thông tin | 6.019 | 64.28% | Không khai báo |
| 2 | Hướng Thành phố | 1.318 | 14.08% | Gộp từ: *Hướng Thành phố, Hướng Đường phố, Hướng Cảnh đêm* |
| 3 | Hướng Biển | 759 | 8.11% | Gộp từ: *Hướng Biển, Hướng Đại dương, Hướng Bãi biển, Hướng Vịnh, Hướng Cảng, Hướng Đầm phá, Hướng biển (một phần), Hướng Đại dương (một phần), Hướng Vịnh biển, Hướng Bến du thuyền* |
| 4 | Hướng Thiên nhiên | 457 | 4.88% | Gộp từ: *Hướng Vườn, Hướng Sân trong, Hướng Công viên, Hướng Thiên nhiên, Hướng Nông thôn* |
| 5 | Hướng Ngoài trời | 239 | 2.55% | Hướng không gian ngoài trời |
| 6 | Hướng Núi | 186 | 1.99% | Gộp từ: *Hướng Núi, Hướng Thắng cảnh, Hướng Thung lũng* |
| 7 | Hướng Sông | 166 | 1.77% | Hướng nhìn ra sông |
| 8 | Hướng Bể bơi | 86 | 0.92% | Hướng nhìn ra hồ bơi |
| 9 | Hướng Hồ | 76 | 0.81% | Gộp từ: *Hướng Hồ, Hướng Hồ (một phần)* |
| 10 | Không có cửa sổ | 58 | 0.62% | Phòng kín / không có cửa sổ hướng ngoại |

---

## 5. Chi Tiết Tiện Ích Phòng (`room_amenities` - Top 30 trên tổng số 87 loại)

Dưới đây là thống kê 30 tiện ích phòng phổ biến nhất được trang bị trong 9.364 phòng. Có thể xem danh sách đầy đủ tại tệp [room_amenities_statistics_normalized.csv](data_csv/room_amenities_statistics_normalized.csv).

| STT | Tiện ích phòng | Số lượng phòng sở hữu | Tỷ lệ (%) |
| :---: | :--- | :---: | :---: |
| 1 | Giải trí | 3.500 | 37.38% |
| 2 | Điều hòa | 3.408 | 36.39% |
| 3 | WiFi miễn phí | 2.892 | 30.88% |
| 4 | TV màn hình phẳng | 2.755 | 29.42% |
| 5 | Bếp | 2.578 | 27.53% |
| 6 | Truyền hình cáp vệ tinh | 2.545 | 27.18% |
| 7 | Tủ lạnh | 2.085 | 22.27% |
| 8 | Cách âm | 1.781 | 19.02% |
| 9 | Ban công sân hiên | 1.719 | 18.36% |
| 10 | Phòng tắm đứng | 1.271 | 13.57% |
| 11 | Điều hòa cá nhân | 1.251 | 13.36% |
| 12 | Giường cũi của em bé theo yêu cầu | 1.120 | 11.96% |
| 13 | Thang máy | 1.107 | 11.82% |
| 14 | Máy pha trà cà phê | 1.064 | 11.36% |
| 15 | Ít gây dị ứng | 785 | 8.38% |
| 16 | Lối đi riêng | 731 | 7.81% |
| 17 | Khu vực ăn uống riêng | 640 | 6.83% |
| 18 | Giường gấp | 583 | 6.23% |
| 19 | Máy rửa bát | 583 | 6.23% |
| 20 | Tầng cao | 577 | 6.16% |
| 21 | Đi lên bằng cầu thang | 574 | 6.13% |
| 22 | Có các phòng thông nhau | 552 | 5.89% |
| 23 | Lối vào hồ bơi | 546 | 5.83% |
| 24 | Tiện nghi bể bơi | 542 | 5.79% |
| 25 | Sưởi | 512 | 5.47% |
| 26 | Dịch vụ phát trực tuyến như netflix | 504 | 5.38% |
| 27 | Nhà vệ sinh phụ | 501 | 5.35% |
| 28 | Không gian làm việc cho máy tính xách tay | 494 | 5.28% |
| 29 | Giường cực dài | 481 | 5.14% |
| 30 | Sử sụng clb thể thao | 471 | 5.03% |

---

## 6. Chi Tiết Nhãn Đánh Giá (`reviews_detail/tags` có mentioned > 4 - 45 loại)

Xếp theo số lượng khách sạn có nhãn này:

| STT | Nhãn đánh giá (Mentioned > 4) | Số khách sạn ghi nhận | Tỷ lệ (%) |
| :---: | :--- | :---: | :---: |
| 1 | Dịch vụ | 424 | 81.54% |
| 2 | Độ sạch sẽ | 422 | 81.15% |
| 3 | Địa điểm | 407 | 78.27% |
| 4 | Độ thoải mái của phòng | 342 | 65.77% |
| 5 | Đáng tiền | 338 | 65.00% |
| 6 | Kích thước phòng | 322 | 61.92% |
| 7 | Bữa sáng | 291 | 55.96% |
| 8 | Nhận phòng | 265 | 50.96% |
| 9 | Hướng nhìn từ phòng | 230 | 44.23% |
| 10 | Bể bơi | 222 | 42.69% |
| 11 | Phòng tắm | 210 | 40.38% |
| 12 | Tiện nghi trong phòng | 183 | 35.19% |
| 13 | Nhiều lựa chọn nhà hàng | 169 | 32.50% |
| 14 | Không khí | 166 | 31.92% |
| 15 | Thiết kế phòng | 164 | 31.54% |
| 16 | Tiện ích tại cơ sở lưu trú | 160 | 30.77% |
| 17 | Bộ đồ giường | 150 | 28.85% |
| 18 | Bãi biển | 142 | 27.31% |
| 19 | Gia đình | 139 | 26.73% |
| 20 | Điều hòa | 133 | 25.58% |
| 21 | Cách âm | 108 | 20.77% |
| 22 | Trả phòng | 91 | 17.50% |
| 23 | Bãi đỗ xe | 65 | 12.50% |
| 24 | Cơ sở vật chất cho trẻ em | 62 | 11.92% |
| 25 | Vòi sen | 54 | 10.38% |
| 26 | Phòng tập | 54 | 10.38% |
| 27 | Đưa đón sân bay | 45 | 8.65% |
| 28 | Khả năng đi bộ thuận tiện | 37 | 7.12% |
| 29 | Nước nóng | 36 | 6.92% |
| 30 | Spa | 34 | 6.54% |
| 31 | Wi-Fi | 30 | 5.77% |
| 32 | Chủ nhà | 30 | 5.77% |
| 33 | Bồn tắm | 29 | 5.58% |
| 34 | Di chuyển | 24 | 4.62% |
| 35 | Bar | 20 | 3.85% |
| 36 | Bữa tối | 19 | 3.65% |
| 37 | Bếp | 16 | 3.08% |
| 38 | Đi công tác | 11 | 2.12% |
| 39 | Cuộc sống về đêm | 9 | 1.73% |
| 40 | Hoạt động không thể bỏ qua | 9 | 1.73% |
| 41 | An toàn | 8 | 1.54% |
| 42 | Cặp đôi | 7 | 1.35% |
| 43 | Thiên nhiên | 5 | 0.96% |
| 44 | Suối nước nóng | 3 | 0.58% |
| 45 | Mua sắm | 3 | 0.58% |

---

## 7. Chi Tiết Phân Loại Địa Điểm Lân Cận (`PLACE_TYPE` - 53 loại)

Thống kê phân phối loại hình địa điểm lân cận từ **4.991 địa điểm** (bảng `nearby_places`):

| STT | Loại địa điểm (PLACE_TYPE) | Số lượng địa điểm | Tỷ lệ (%) |
| :---: | :--- | :---: | :---: |
| 1 | Bệnh Viện và Cơ Sở Y Tế | 830 | 16.63% |
| 2 | Siêu Thị | 616 | 12.34% |
| 3 | Trung Tâm và Khu Mua Sắm | 406 | 8.13% |
| 4 | Sân Bay | 380 | 7.61% |
| 5 | Công Viên Công Cộng | 309 | 6.19% |
| 6 | Địa điểm giải trí | 205 | 4.11% |
| 7 | Bãi Biển | 160 | 3.21% |
| 8 | Nơi Thờ Cúng | 135 | 2.70% |
| 9 | Đài Kỷ Niệm và Di Tích Lịch Sử | 131 | 2.62% |
| 10 | Quán Rượu | 124 | 2.48% |
| 11 | Sông và Hồ | 119 | 2.38% |
| 12 | Viện Bảo Tàng và Phòng Trưng Bày Nghệ Thuật | 115 | 2.30% |
| 13 | Trung tâm thể thao và Yoga | 97 | 1.94% |
| 14 | Núi, đồi và hang động | 94 | 1.88% |
| 15 | Nơi Biểu Diễn Văn Nghệ | 82 | 1.64% |
| 16 | Đại Sứ Quán và Lãnh Sự Quán | 79 | 1.58% |
| 17 | Công Viên Giải Trí | 70 | 1.40% |
| 18 | Các Sân Thể Thao | 69 | 1.38% |
| 19 | Đảo | 67 | 1.34% |
| 20 | Cửa Hiệu | 66 | 1.32% |
| 21 | Bãi đỗ xe | 61 | 1.22% |
| 22 | Điểm Cắm Trại và Vui Chơi Ngoài Trời | 59 | 1.18% |
| 23 | Ngân Hàng và Quầy Đổi Ngoại Tệ | 57 | 1.14% |
| 24 | Điểm Tham Quan | 57 | 1.14% |
| 25 | Trường Cao Đẳng và Đại Học | 48 | 0.96% |
| 26 | Ga Tàu Hoả, Ga Tàu Điện Ngầm và Bến Xe Buýt | 43 | 0.86% |
| 27 | Phố Nổi Tiếng | 41 | 0.82% |
| 28 | Dịch Vụ Internet, Bưu Chính và Điện Thoại | 40 | 0.80% |
| 29 | Tòa Nhà Nổi Tiếng | 39 | 0.78% |
| 30 | Bến Cảng và Bến Đò | 34 | 0.68% |
| 31 | Thông Tin Du Lịch và Du Hành | 34 | 0.68% |
| 32 | Công Viên Quốc Gia | 33 | 0.66% |
| 33 | Sân Gôn | 32 | 0.64% |
| 34 | Vườn Bách Thảo và Vườn Thú | 31 | 0.62% |
| 35 | Trung tâm Thể thao và Bể bơi | 31 | 0.62% |
| 36 | Cao Ốc Văn Phòng | 30 | 0.60% |
| 37 | Spa | 23 | 0.46% |
| 38 | Phương Tiện Vận Chuyển | 23 | 0.46% |
| 39 | Cầu | 22 | 0.44% |
| 40 | Chợ | 20 | 0.40% |
| 41 | Trung Tâm Hội Nghị và Triển Lãm | 18 | 0.36% |
| 42 | Tòa Nhà Lịch Sử | 14 | 0.28% |
| 43 | Sòng Bạc | 10 | 0.20% |
| 44 | Suối nước nóng và thác nước tự nhiên | 9 | 0.18% |
| 45 | Vịnh | 6 | 0.12% |
| 46 | Nhà hát | 6 | 0.12% |
| 47 | Bến Du Thuyền | 6 | 0.12% |
| 48 | Thư Viện | 4 | 0.08% |
| 49 | Đồn Cảnh Sát và Dịch Vụ Khẩn Cấp | 2 | 0.04% |
| 50 | Nghĩa Trang | 1 | 0.02% |
| 51 | Nhà máy rượu | 1 | 0.02% |
| 52 | Các Sân Bay và Bãi Đáp Trực Thăng | 1 | 0.02% |
| 53 | Nơi Biểu Diễn Âm Nhạc | 1 | 0.02% |
