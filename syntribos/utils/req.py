from urlparse import urlparse


def format_proxies(url):
    """Format proxies required by requests module"""
    if not url:
        return None
    parsed_url = urlparse(url)
    host = parsed_url.hostname
    scheme = parsed_url.scheme
    if host and scheme:
        return {
            scheme: url
        }
    return None
