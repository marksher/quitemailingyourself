import ipaddress, socket, httpx, re
from bs4 import BeautifulSoup

PRIVATE_NETS = [ipaddress.ip_network(n) for n in [
    "10.0.0.0/8","172.16.0.0/12","192.168.0.0/16","127.0.0.0/8","169.254.0.0/16","::1/128","fc00::/7","fe80::/10"
]]

def is_private_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
        for _,_,_,_,addr in infos:
            ip = ipaddress.ip_address(addr[0])
            if any(ip in net for net in PRIVATE_NETS):
                return True
        return False
    except Exception:
        return True

async def fetch_html(url: str, timeout: float = 10.0, max_bytes: int = 2_000_000) -> str:
    if not url.startswith(("http://","https://")):
        raise ValueError("invalid scheme")
    host = url.split("/")[2].split("@")[-1].split(":")[0]
    if is_private_host(host):
        raise ValueError("blocked host")
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        r = await client.get(url, headers={"User-Agent":"Pocketish/1.0"})
        r.raise_for_status()
        return r.text[:max_bytes]

def extract_content(html: str, title_hint: str = ""):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script","style","noscript"]): tag.decompose()
    title = (soup.find("meta", property="og:title") or {}).get("content") or (soup.title.string if soup.title else "") or title_hint
    desc = (soup.find("meta", property="og:description") or {}).get("content") or ""
    body = " ".join(t.strip() for t in soup.get_text(" ").split())
    return title[:300], desc[:500], body
