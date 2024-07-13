import asyncio
import concurrent.futures
import json
import os
import re
import time
import requests
from functools import partial
import tweepy
from datetime import datetime, timedelta
import random

from communex.client import CommuneClient  # type: ignore
from communex.module.client import ModuleClient  # type: ignore
from communex.module.module import Module  # type: ignore
from communex.types import Ss58Address  # type: ignore
from substrateinterface import Keypair  # type: ignore

from ._config import ValidatorSettings
from utils.utils import log

IP_REGEX = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+")


def set_weights(
        settings: ValidatorSettings,
        score_dict: dict[
            int, float
        ],
        netuid: int,
        client: CommuneClient,
        key: Keypair,
) -> None:
    score_dict = cut_to_max_allowed_weights(score_dict, settings.max_allowed_weights)
    weighted_scores: dict[int, int] = {}
    scores = sum(score_dict.values())
    for uid, score in score_dict.items():
        weight = int(score / scores * 10000)
        weighted_scores[uid] = weight

    weighted_scores = {k: v for k, v in weighted_scores.items() if v != 0}
    uids = list(weighted_scores.keys())
    weights = list(weighted_scores.values())
    client.vote(key=key, uids=uids, weights=weights, netuid=netuid)


def cut_to_max_allowed_weights(
        score_dict: dict[int, float], max_allowed_weights: int
) -> dict[int, float]:
    sorted_scores = sorted(score_dict.items(), key=lambda x: x[1], reverse=True)
    cut_scores = sorted_scores[:max_allowed_weights]
    return dict(cut_scores)


def extract_address(string: str):
    return re.search(IP_REGEX, string)


def get_subnet_netuid(clinet: CommuneClient, subnet_name: str = "market-compass"):
    subnets = clinet.query_map_subnet_names()
    for netuid, name in subnets.items():
        if name == subnet_name:
            return netuid
    raise ValueError(f"Subnet {subnet_name} not found")


def get_ip_port(modules_adresses: dict[int, str]):
    filtered_addr = {id: extract_address(addr) for id, addr in modules_adresses.items()}
    ip_port = {
        id: x.group(0).split(":") for id, x in filtered_addr.items() if x is not None
    }
    return ip_port

class SelfTwitterValidator(Module):
    def __init__(
            self,
            key: Keypair,
            netuid: int,
            client: CommuneClient,
            call_timeout: int = 3,

    ) -> None:
        super().__init__()
        self.client = client
        self.key = key
        self.netuid = netuid
        self.call_timeout = call_timeout
        self.mc_subnet_url = os.getenv('MC_SUBNET_API_URL')
        self.twitter_client = tweepy.Client(bearer_token=os.getenv('MC_BEARER_TOKEN'))
        self.query_counts = {}
        self.last_global_execution_time = 0
        self.global_time_elapsed = 0
        self.blacklist = {}

    def get_addresses(self, client: CommuneClient, netuid: int) -> dict[int, str]:
        module_addreses = client.query_map_address(netuid)
        return module_addreses

    async def get_votes(self) -> list[str]:
        response = requests.get(f'{self.mc_subnet_url}/subnet/getLatestVoting')
        if response.ok:
            return response.json()
        raise Exception("cant get latest voting")

    async def get_prompts(self, count: int) -> list[str]:
        response = requests.get(f'{self.mc_subnet_url}/subnet/getNextOpenRequests?count={count}')
        if response.ok:
            return response.json()
        raise Exception("cant get prompt")

    def _get_miner_prediction(
                self,
                all_prompts: list,
                miner_info: tuple[int, tuple[list[str], Ss58Address]],
        ) -> str | None:
            miner_index, [connection, miner_key] = miner_info
            module_ip, module_port = connection
            client = ModuleClient(module_ip, int(module_port), self.key)
            prompt = all_prompts[miner_index]['query']

            try:
                miner_answer = asyncio.run(
                    client.call(
                        "generate",
                        miner_key,
                        {"prompt": prompt},
                        timeout=self.call_timeout,  #  type: ignore
                    )
                )

            except Exception as e:
                log(f"Miner {module_ip}:{module_port} failed to generate an answer")
                print(e)
                miner_answer = None
            return miner_answer

    def is_ninety_percent_match(self, arr1, arr2):
        percentage = self.get_matching_percentage(arr1, arr2)
        return percentage >= 90

    def get_matching_percentage(self, arr1, arr2):
        if not arr1 or not arr2:
            return 0

        matches = 0
        arr2_texts = [tweet['text'] for tweet in arr2]

        for tweet1 in arr1:
            if tweet1['text'] in arr2_texts:
                matches += 1

        percentage = (matches / len(arr1)) * 100
        return percentage


    async def check_miner_response(self, content: str, miner_id: str, prompt: str) -> int:
        self.query_counts[miner_id] = self.query_counts.get(miner_id, 0) + 1
        current_time = int(datetime.utcnow().timestamp() * 1000)
        self.global_time_elapsed = current_time - self.last_global_execution_time

        if miner_id in self.blacklist:
            return 0.05

        if (self.query_counts[miner_id] > 0 or random.random() < 0.01) and self.global_time_elapsed > 10000:
            self.last_global_execution_time = current_time
            passed = await self.query_twitter_and_check(content, miner_id, prompt)
            if not passed:
                self.blacklist[miner_id] = datetime.utcnow().timestamp() * 1000
                return 0.05

        return 1

    async def query_twitter_and_check(self, user_content, miner_id, prompt):
        user_start_time = user_content[0]['created_at']
        user_start_date = datetime.strptime(user_start_time, "%Y-%m-%dT%H:%M:%S.%fZ")
        current_date = datetime.utcnow()
        diff_in_minutes = (current_date - user_start_date).total_seconds() / 60.0
        is_diff_longer_than_half_minute = diff_in_minutes > 0.5

        options = {
            "max_results": 50,
            "start_time": '2024-04-01T05:00:00Z',
            "user.fields": "id",
            "tweet.fields": "created_at"
        }

        if not is_diff_longer_than_half_minute:
            options["end_time"] = user_start_time

        js_tweets = self.twitter_client.search_all_tweets(prompt, **options)
        tweets = [tweet.data for tweet in js_tweets.data]

        passed = self.is_ninety_percent_match(tweets, user_content)
        self.query_counts[miner_id] = 0
        if not passed:
            self.blacklist[miner_id] = datetime.utcnow().timestamp() * 1000
            return 0.05


        return 1

    async def validate_step(
            self, syntia_netuid: int, settings: ValidatorSettings
    ) -> None:

        modules_adresses = self.get_addresses(self.client, syntia_netuid)
        modules_keys = self.client.query_map_key(syntia_netuid)
        val_ss58 = self.key.ss58_address
        if val_ss58 not in modules_keys.values():
            raise RuntimeError(f"validator key {val_ss58} is not registered in subnet")

        modules_info: dict[int, tuple[list[str], Ss58Address]] = {}

        modules_filtered_address = get_ip_port(modules_adresses)
        for module_id in modules_keys.keys():
            module_addr = modules_filtered_address.get(module_id, None)
            if not module_addr:
                continue

            modules_info[module_id] = (module_addr, modules_keys[module_id])

        score_dict: dict[int, float] = {}

        log(f"Selected the following miners: {modules_info.keys()}")

        try:
            all_prompts = await self.get_prompts(len(modules_info.values()))
        except Exception as e:
            print('problem with getting prompts', e)
            return

        with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
            get_miner_prediction = partial(self._get_miner_prediction, all_prompts)
            it = executor.map(get_miner_prediction, enumerate(modules_info.values()))
            miner_answers = [*it]

        for index, [mid, miner_response] in enumerate(zip(modules_info.keys(), miner_answers)):
            miner_answer = miner_response
            used_prompt = all_prompts[index]['query']
            print(used_prompt)

            if not miner_answer:
                log(f"Skipping miner {mid} that didn't answer")
                continue

            score = await self.check_miner_response(miner_answer, mid, used_prompt)
            print('Score from validation. UID:', mid, score)

            time.sleep(0.5)
            # score has to be lower or eq to 1, as one is the best score, you can implement your custom logic
            if score <= 1:
                score_dict[mid] = score
            else:
                print('WARN: score > 1. Uid:', mid, score)

        if not score_dict:
            log("No miner managed to give a valid answer")
            return None

        print('all scores', score_dict.items())

        _ = set_weights(settings, score_dict, self.netuid, self.client, self.key)

    def validation_loop(self, settings: ValidatorSettings) -> None:
        """
        Run the validation loop continuously based on the provided settings.

        Args:
            settings: The validator settings to use for the validation loop.
        """

        while True:
            start_time = time.time()
            _ = asyncio.run(self.validate_step(self.netuid, settings))

            elapsed = time.time() - start_time
            if elapsed < settings.iteration_interval:
                sleep_time = settings.iteration_interval - elapsed
                log(f"Sleeping for {sleep_time}")
                time.sleep(sleep_time)
