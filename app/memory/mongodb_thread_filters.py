from chainlit.types import Pagination, ThreadDict, ThreadFilter


def filter_threads(threads: list, filters: ThreadFilter) -> list:
    search_keyword = filters.search.lower() if filters.search else None
    feedback_value = int(filters.feedback) if filters.feedback else None
    if not search_keyword and feedback_value is None:
        return threads
    return [t for t in threads if _matches_thread(t, search_keyword, feedback_value)]


def paginate(threads: list, pagination: Pagination) -> tuple[list, bool]:
    start = 0
    if pagination.cursor:
        for i, thread in enumerate(threads):
            if thread["id"] == pagination.cursor:
                start = i + 1
                break
    end = start + pagination.first
    return threads[start:end] or [], len(threads) > end


def _matches_thread(
    thread: ThreadDict, search_keyword: str | None, feedback_value
) -> bool:
    if search_keyword and not any(
        search_keyword in step.get("output", "").lower() for step in thread["steps"]
    ):
        return False
    if feedback_value is None:
        return True
    return any(
        (fb := step.get("feedback")) and fb.get("value") == feedback_value
        for step in thread["steps"]
    )
