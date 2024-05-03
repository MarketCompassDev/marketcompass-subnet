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
from src.subnet.utils.utils import log

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
    # you can replace with `max_allowed_weights` with the amount your subnet allows
    score_dict = cut_to_max_allowed_weights(score_dict, settings.max_allowed_weights)

    # Create a new dictionary to store the weighted scores
    weighted_scores: dict[int, int] = {}

    # Calculate the sum of all inverted scores
    scores = sum(score_dict.values())

    # process the scores into weights of type dict[int, int]
    # Iterate over the items in the score_dict
    for uid, score in score_dict.items():
        # Calculate the normalized weight as an integer
        weight = int(score / scores * 100)

        # Add the weighted score to the new dictionary
        weighted_scores[uid] = weight

    # filter out 0 weights
    weighted_scores = {k: v for k, v in weighted_scores.items() if v != 0}

    uids = list(weighted_scores.keys())
    weights = list(weighted_scores.values())
    # send the blockchain call
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
    """
    Retrieve the network UID of the subnet.

    Args:
        client: The CommuneX client.
        subnet_name: The name of the subnet (default: "foo").

    Returns:
        The network UID of the subnet.

    Raises:
        ValueError: If the subnet is not found.
    """

    subnets = clinet.query_map_subnet_names()
    for netuid, name in subnets.items():
        if name == subnet_name:
            return netuid
    raise ValueError(f"Subnet {subnet_name} not found")


def get_ip_port(modules_adresses: dict[int, str]):
    """
    Get the IP and port information from module addresses.

    Args:
        modules_addresses: A dictionary mapping module IDs to their addresses.

    Returns:
        A dictionary mapping module IDs to their IP and port information.
    """

    filtered_addr = {id: extract_address(addr) for id, addr in modules_adresses.items()}
    ip_port = {
        id: x.group(0).split(":") for id, x in filtered_addr.items() if x is not None
    }
    return ip_port


class TwitterValidator(Module):
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
        self.mc_subnet_api_x_api_key = os.getenv('MC_SUBNET_API_X_API_KEY')
        self.mc_subnet_url = os.getenv('MC_SUBNET_API_URL')

    def get_addresses(self, client: CommuneClient, netuid: int) -> dict[int, str]:
        """
        Retrieve all module addresses from the subnet.

        Args:
            client: The CommuneClient instance used to query the subnet.
            netuid: The unique identifier of the subnet.

        Returns:
            A dictionary mapping module IDs to their addresses.
        """

        # Makes a blockchain query for the miner addresses
        module_addreses = client.query_map_address(netuid)
        return module_addreses

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
            miner_answer = miner_answer

        except Exception as e:
            log(f"Miner {module_ip}:{module_port} failed to generate an answer")
            print(e)
            miner_answer = None
        return miner_answer

    async def get_blacklisted_ids(self) -> set[str]:
        response = requests.get(f'{self.mc_subnet_url}/subnet/blacklistedIds')
        if response.ok:
            return set(response.json())
        raise Exception("cant get BL")

    async def get_prompts(self, count: int) -> list[str]:
        response = requests.get(f'{self.mc_subnet_url}/subnet/getNextRequests?count={count}', headers={
            'x-api-key': self.mc_subnet_api_x_api_key
        })
        if response.ok:
            return response.json()
        raise Exception("cant get prompt")

    async def register_response_get_weight(self, content: str, miner_id: str, prompt_id: str) -> int:
        response = requests.post(
            f'{self.mc_subnet_url}/subnet/registerResponse',
            data={
                "content": json.dumps(content),
                "minerId": miner_id,
                "promptId": prompt_id
            },
            headers={
                'x-api-key': self.mc_subnet_api_x_api_key
            }
        )
        if response.ok:
            return float(response.text)
        return 0

    async def validate_step(
            self, syntia_netuid: int, settings: ValidatorSettings
    ) -> None:

        black_listed_ids = await self.get_blacklisted_ids()

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

            if module_id not in black_listed_ids:
                modules_info[module_id] = (module_addr, modules_keys[module_id])

        score_dict: dict[int, float] = {}

        log(f"Selected the following miners: {modules_info.keys()}")

        try:
            all_prompts = await self.get_prompts(len(modules_info.values()))
        except Exception as e:
            print('problem with getting prompts', e)
            return

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            get_miner_prediction = partial(self._get_miner_prediction, all_prompts)
            it = executor.map(get_miner_prediction, enumerate(modules_info.values()))
            miner_answers = [*it]

        for index, [mid, miner_response] in enumerate(zip(modules_info.keys(), miner_answers)):
            miner_answer = miner_response
            used_prompt_id = all_prompts[index]['promptId']

            if not miner_answer:
                log(f"Skipping miner {mid} that didn't answer")
                continue

            score = await self.register_response_get_weight(miner_answer, mid, used_prompt_id)
            print('score from backend. UID:', mid, score)

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

        # the blockchain call to set the weights
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
