"""Task 18 bước 2: ghép file theo mẫu tên (spec 10 mục 4.3, mục 13)."""

from __future__ import annotations

from app.services.batch_matcher import match, normalize_name


class TestNormalizeName:
    def test_strips_extension_and_diacritics(self):
        assert normalize_name("Báo cáo DTP.xlsx") == "BAOCAODTP"

    def test_removes_separators(self):
        assert normalize_name("hoa-don_tac.nghiep 2026.xlsx") == "HOADONTACNGHIEP2026"

    def test_keeps_digits(self):
        assert normalize_name("DTP_2026-10.xlsx") == "DTP202610"

    def test_diacritics_variants(self):
        assert normalize_name("HÓA ĐƠN.xlsx") == "HOADON"
        assert normalize_name("đơn.xlsx") == "DON"

    def test_empty_and_plain(self):
        assert normalize_name("") == ""
        assert normalize_name("ABC123") == "ABC123"

    def test_nested_path_keeps_filename_only(self):
        assert normalize_name("thu muc/Bao cao.xlsx") == "BAOCAO"


class TestMatch:
    ITEMS = [
        {"item_id": 1, "pattern": "*DTP*"},
        {"item_id": 2, "pattern": "*HOA_DON*"},
        {"item_id": 3, "pattern": "*LUONG*|*HOA_DON_TAC_NGHIEP*"},
    ]

    def test_single_match(self):
        assert match("dtp_2026-10.xlsx", self.ITEMS) == [1]

    def test_no_match(self):
        assert match("bao_cao_thue.xlsx", self.ITEMS) == []

    def test_multiple_match_is_ambiguous(self):
        assert match("DTP_HOA_DON_TAC_NGHIEP.xlsx", self.ITEMS) == [1, 2, 3]

    def test_multi_pattern_with_pipe(self):
        assert match("hoa_don_tac_nghiep_10.xlsx", self.ITEMS) == [2, 3]

    def test_pattern_normalized_like_name(self):
        items = [{"item_id": 9, "pattern": "*HÓA-ĐƠN*"}]
        assert match("hoa_don_10.xlsx", items) == [9]

    def test_empty_pattern_matches_nothing(self):
        assert match("dtp.xlsx", [{"item_id": 1, "pattern": ""}]) == []

    def test_exact_pattern_without_wildcard(self):
        items = [{"item_id": 5, "pattern": "DTP202610"}]
        assert match("DTP_2026-10.xlsx", items) == [5]
        assert match("DTP_2026-11.xlsx", items) == []
