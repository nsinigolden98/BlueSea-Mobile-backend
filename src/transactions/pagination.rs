//! Pagination for wallet history. Mirrors
//! `transactions/pagination.py::WalletTransactionPagination`
//! (default 5 per page, `?page=` / `?page_size=`, max 50) and DRF's
//! `{count, next, previous, results}` envelope with absolute URLs.

pub const DEFAULT_PAGE_SIZE: i64 = 5;
pub const MAX_PAGE_SIZE: i64 = 50;

#[derive(Debug, Clone, Copy)]
pub struct Page {
    pub number: i64,
    pub size: i64,
}

impl Page {
    pub fn from_query(page: Option<i64>, page_size: Option<i64>) -> Self {
        Self {
            number: page.filter(|&p| p >= 1).unwrap_or(1),
            size: page_size
                .filter(|&s| s >= 1)
                .map(|s| s.min(MAX_PAGE_SIZE))
                .unwrap_or(DEFAULT_PAGE_SIZE),
        }
    }

    pub fn offset(&self) -> i64 {
        (self.number - 1) * self.size
    }

    pub fn total_pages(&self, count: i64) -> i64 {
        if count <= 0 {
            1
        } else {
            (count + self.size - 1) / self.size
        }
    }
}

/// Build DRF-style absolute `next`/`previous` links, preserving all
/// original query params except `page` (like DRF keeps its filters).
pub fn page_url(
    scheme: &str,
    host: &str,
    path: &str,
    raw_query: &str,
    page: i64,
    page_size: i64,
) -> String {
    let mut pairs: Vec<(String, String)> = raw_query
        .split('&')
        .filter(|s| !s.is_empty())
        .filter_map(|s| {
            s.split_once('=')
                .map(|(k, v)| (k.to_string(), v.to_string()))
        })
        .filter(|(k, _)| k != "page" && k != "page_size")
        .collect();
    pairs.push(("page".to_string(), page.to_string()));
    pairs.push(("page_size".to_string(), page_size.to_string()));
    let query = pairs
        .iter()
        .map(|(k, v)| format!("{k}={v}"))
        .collect::<Vec<_>>()
        .join("&");
    format!("{scheme}://{host}{path}?{query}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn page_math_and_links() {
        let p = Page::from_query(None, None);
        assert_eq!((p.number, p.size, p.offset()), (1, 5, 0));
        let p = Page::from_query(Some(3), Some(200));
        assert_eq!((p.number, p.size, p.offset()), (3, 50, 100));
        assert_eq!(p.total_pages(101), 3);
        let url = page_url("http", "h:8000", "/transactions/history/", "page_size=5", 2, 5);
        assert_eq!(url, "http://h:8000/transactions/history/?page=2&page_size=5");
    }
}
