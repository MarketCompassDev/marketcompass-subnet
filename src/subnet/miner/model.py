import os
import requests

from communex.module import Module, endpoint
from communex.key import generate_keypair
from keylimiter import TokenBucketLimiter


class Miner(Module):
    def __init__(self):
        super().__init__()
        self.bearer_token = os.getenv('MC_BEARER_TOKEN')

    @endpoint
    def generate(self, prompt: str, start_time: str = '2024-04-01T5:00:00Z', max_results: int = 50):
        # TODO: pass start_time, max_results from validator
        url = "https://api.twitter.com/2/tweets/search/all"

        def bearer_oauth(r):
            r.headers["Authorization"] = f"Bearer {self.bearer_token}"
            r.headers["User-Agent"] = "v2FullArchiveSearchPython"
            return r

        response = requests.request("GET", url, auth=bearer_oauth, params={
            'query': prompt,
            "max_results": max_results,
            "start_time": start_time,
            "user.fields": "id,username,name",
            "tweet.fields": "created_at,author_id"
        })

        if response.ok:
            tweets = response.json()
            return tweets['data']
        raise Exception(f"Cant get tweets for prompt '{prompt}'")


if __name__ == "__main__":
    from communex.module.server import ModuleServer
    import uvicorn

    key = generate_keypair()
    miner = Miner()
    refill_rate = 1 / 400
    bucket = TokenBucketLimiter(2, refill_rate)
    server = ModuleServer(miner, key, ip_limiter=bucket, subnets_whitelist=[17])
    app = server.get_fastapi_app()

    # Only allow local connections
    uvicorn.run(app, host="0.0.0.0", port=8000)
