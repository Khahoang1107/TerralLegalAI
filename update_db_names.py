import psycopg2
import json

mapping = {
    "ky_tinh_thue_nam": "Kỳ tính thuế năm",
    "lan_dau": "Khai lần đầu",
    "bo_sung_lan_thu": "Bổ sung lần thứ",
    "ho_ten_nguoi_nop_thue": "Họ tên người nộp thuế",
    "ngay_thang_nam_sinh_nguoi_nop_thue": "Ngày tháng năm sinh",
    "ma_so_thue": "Mã số thuế",
    "so_cmt_cccd_ho_chieu_nguoi_nop_thue": "Số CMND/CCCD",
    "ngay_thang_nam_cap_cccd": "Ngày cấp",
    "noi_cap_cmt_cccd_ho_chieu_nguoi_nop_thue": "Nơi cấp",
    "so_nha_dia_chi_cu_tru": "Số nhà",
    "duong_pho_dia_chi_cu_tru": "Đường phố",
    "to_thon_dia_chi_cu_tru": "Tổ/thôn",
    "phuong_xa_thi_tran_dia_chi_cu_tru": "Phường/xã/thị trấn",
    "quan_huyen_dia_chi_cu_tru": "Quận/huyện",
    "dia_chi_nhan_thong_bao_thue": "Địa chỉ nhận thông báo thuế",
    "dien_thoai_nguoi_nop_thue": "Điện thoại",
    "ten_dai_ly_thue": "Tên đại lý thuế",
    "ma_so_thue_dai_ly_thue": "Mã số thuế đại lý",
    "so_hop_dong_dai_ly_thue": "Số hợp đồng",
    "ngay_hop_dong_dai_ly_thue": "Ngày hợp đồng",
    "ho_ten_dong_so_huu_1": "Họ tên đồng sở hữu 1",
    "mst_dong_so_huu_1": "MST đồng sở hữu 1",
    "cmt_cccd_ho_chieu_dong_so_huu_1": "CMND đồng sở hữu 1",
    "ty_le_dong_so_huu_1": "Tỷ lệ đồng sở hữu 1",
    "ho_ten_dong_so_huu_2": "Họ tên đồng sở hữu 2",
    "mst_dong_so_huu_2": "MST đồng sở hữu 2",
    "cmt_cccd_ho_chieu_dong_so_huu_2": "CMND đồng sở hữu 2",
    "ty_le_dong_so_huu_2": "Tỷ lệ đồng sở hữu 2",
    "ho_ten_dong_so_huu_3": "Họ tên đồng sở hữu 3",
    "mst_dong_so_huu_3": "MST đồng sở hữu 3",
    "cmt_cccd_ho_chieu_dong_so_huu_3": "CMND đồng sở hữu 3",
    "ty_le_dong_so_huu_3": "Tỷ lệ đồng sở hữu 3",
    "thong_tin_bo_sung_dong_so_huu": "Thông tin bổ sung",
    "so_nha_thua_dat": "Số nhà (thửa đất)",
    "duong_pho_thua_dat": "Đường phố (thửa đất)",
    "to_thon_thua_dat": "Tổ/thôn (thửa đất)",
    "phuong_xa_thi_tran_thua_dat": "Phường/xã (thửa đất)",
    "quan_huyen_thua_dat": "Quận/huyện (thửa đất)",
    "tinh_thanh_pho_thua_dat": "Tỉnh/thành phố (thửa đất)",
    "la_thua_duy_nhat": "Là thửa duy nhất",
    "quan_huyen_dk_ke_khai_tong_hop": "Quận/huyện ĐK kê khai",
    "da_co_giay_chung_nhan": "Đã có giấy chứng nhận",
    "so_giay_chung_nhan_dat": "Số giấy chứng nhận",
    "ngay_cap_giay_chung_nhan_dat": "Ngày cấp GCN",
    "thua_dat_so": "Thửa đất số",
    "to_ban_do_so": "Tờ bản đồ số",
    "dien_tich_tren_gcn": "Diện tích trên GCN",
    "loai_dat_muc_dich_su_dung_tren_gcn": "Mục đích sử dụng trên GCN",
    "dien_tich_su_dung_dung_muc_dich": "DT sử dụng đúng mục đích",
    "dien_tich_su_dung_sai_muc_dich_chua_su_dung": "DT sử dụng sai mục đích",
    "han_muc_dat_su_dung": "Hạn mức đất sử dụng",
    "dien_tich_dat_lan_chiem": "DT đất lấn chiếm",
    "chua_co_giay_xac_nhan": "Chưa có giấy xác nhận",
    "dien_tich_dat_chua_co_gcn": "DT đất chưa có GCN",
    "loai_dat_muc_dich_dang_su_dung_chua_co_gcn": "Mục đích sử dụng (chưa GCN)",
    "thoi_diem_bat_dau_su_dung_dat": "Thời điểm bắt đầu SD",
    "ngay_thay_doi_thong_tin_thua_dat": "Ngày thay đổi thông tin",
    "loai_nha_nhieu_tang_chung_cu": "Loại nhà nhiều tầng/chung cư",
    "dien_tich_san_thuc_te_nha_nhieu_tang_chung_cu": "Diện tích sàn thực tế",
    "he_so_phan_bo_nha_nhieu_tang_chung_cu": "Hệ số phân bổ",
    "truong_hop_mien_giam_thue": "Trường hợp miễn giảm thuế",
}

conn = psycopg2.connect(host='localhost', port=5432, dbname='terralegal', user='terralegal_user', password='terralegal_pass_dev')
cur = conn.cursor()
cur.execute("SELECT fields FROM form_schemas WHERE id = '83e2efc7-6e5d-46b0-8a62-e70aeb311d5e'")
fields = cur.fetchone()[0]

for f in fields:
    if f['name'] in mapping:
        f['name'] = mapping[f['name']]

cur.execute("UPDATE form_schemas SET fields = %s WHERE id = '83e2efc7-6e5d-46b0-8a62-e70aeb311d5e'", (json.dumps(fields, ensure_ascii=False),))
conn.commit()
print("Updated fields.")
