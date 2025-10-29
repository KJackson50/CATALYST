from src.dnac_client import DNACClient

def test_client_init():
    c = DNACClient("https://example", "u", "p")
    assert c.base_url == "https://example"