"""
测试分页工具（app/core/pagination.py）
"""
from app.core.pagination import PageParams, PageResponse


class TestPageParams:
    def test_defaults(self):
        params = PageParams()

        assert params.page == 1
        assert params.page_size == 20
        assert params.offset == 0
        assert params.limit == 20

    def test_offset_and_limit(self):
        params = PageParams(page=3, page_size=10)

        assert params.offset == 20
        assert params.limit == 10


class TestPageResponse:
    def test_has_next_and_prev(self):
        first = PageResponse(items=[], total=55, page=1, page_size=20, total_pages=3)
        middle = PageResponse(items=[], total=55, page=2, page_size=20, total_pages=3)
        last = PageResponse(items=[], total=55, page=3, page_size=20, total_pages=3)

        assert (first.has_next, first.has_prev) == (True, False)
        assert (middle.has_next, middle.has_prev) == (True, True)
        assert (last.has_next, last.has_prev) == (False, True)

    def test_single_page_has_no_navigation(self):
        only = PageResponse(items=[], total=5, page=1, page_size=20, total_pages=1)

        assert only.has_next is False
        assert only.has_prev is False
