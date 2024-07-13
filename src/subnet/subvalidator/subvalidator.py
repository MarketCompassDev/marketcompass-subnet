import asyncio
import concurrent.futures
import json
import os
import re
import time
import requests
from functools import partial

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

    print('scoreDict:', score_dict)
    score_dict = cut_to_max_allowed_weights(score_dict, settings.max_allowed_weights)
    print('scoreDict2:', score_dict)
    weighted_scores: dict[int, int] = {}
    scores = sum(score_dict.values())
    print(scores)
    for uid, score in score_dict.items():
        weight = int(score / scores * 10000)
        weighted_scores[uid] = weight

    weighted_scores = {k: v for k, v in weighted_scores.items() if v != 0}
    uids = list(weighted_scores.keys())
    weights = list(weighted_scores.values())
    print(uids)
    print(weights)
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


class SubTwitterValidator(Module):
    def __init__(
            self,
            key: Keypair,
            netuid: int,
            client: CommuneClient,
            call_timeout: int = 60,

    ) -> None:
        super().__init__()
        self.client = client
        self.key = key
        self.netuid = netuid
        self.call_timeout = call_timeout
        self.mc_subnet_url = os.getenv('MC_SUBNET_API_URL')

    async def get_votes(self) -> list[str]:
        response = requests.get(f'{self.mc_subnet_url}/subnet/getLatestVoting')
        if response.ok:
            return response.json()
        raise Exception("cant get latest voting")

    async def validate_step(
            self, mc_netuid: int, settings: ValidatorSettings
    ) -> None:

        score_dict: dict[int, float] = {}

        try:
            all_votes = await self.get_votes()
            print(all_votes)
        except Exception as e:
            print('problem with getting latest voting', e)
            return

        score_dict = all_votes

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
