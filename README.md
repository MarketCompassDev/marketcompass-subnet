---

# Market Compass Subnet

This is the Market Compass Subnet, built on top of [CommuneX](https://github.com/agicommies/communex). Learn how to structure, build, and deploy a subnet on [Commune AI](https://communeai.org/)!

You can find detailed information about the project on our [project page](https://marketcompass.ai).
- Documentation is available [here](https://docs.marketcompass.ai/subnet/subnet-17).
- Subnet miners statistics can be found [here](http://stats.subnet.marketcompass.ai).
- A early swagger version of data retrieval from miners is available [here](https://data.marketcompass.ai/swagger).


## Environment Variables for Miner

### MC_BEARER_TOKEN
Bearer token for Twitter Pro API.

Set it with:
```sh
export MC_BEARER_TOKEN=YOUR_BEARER_TOKEN
```

### MC_SUBNET_API_URL
URL for the current version of the API.

Set it with:
```sh
export MC_SUBNET_API_URL=https://api3.subnet.marketcompass.ai
```

## Dependencies

The entire subnet is built on top of the [CommuneX library / SDK](https://github.com/agicommies/communex), which is the primary dependency. You can find the complete list of dependencies in the [requirements.txt](requirements.txt) file.

Here are the main dependencies:
```txt
communex
typer
uvicorn
keylimiter
pydantic-settings
```

## Running the Miner

From the root of your project, start the miner with the following command:
```sh
comx module serve subnet.miner.model.Miner <your-com-key> --subnets-whitelist 17 --ip 0.0.0.0 --port 8000
```

To register the miner, use:
```sh
comx module register <your-miner-name> <your-com-key> --ip <your-server-ip> --port 8000 --netuid 17
```

## Quick Start for Validator

1. Clone the repository:
    ```sh
    git clone https://github.com/MarketCompassDev/marketcompass-subnet.git
    ```

2. Install required libraries:
    ```sh
    apt install python3-pip
    pip install poetry
    pip install communex --upgrade
    apt install nodejs
    apt install npm
    npm install pm2 -g
    ```

3. Go to the project directory and install dependencies:
    ```sh
    cd marketcompass-subnet
    pip install -r requirements.txt
    cd src/subnet
    ```

4. Register the validator:
    ```sh
    comx module register YOUR_VALI_NAME YOUR_VALI_KEY --netuid 17
    # Example:
    # comx module register market-compass::vali1 mykey --netuid 17
    export MC_SUBNET_API_URL=https://api3.subnet.marketcompass.ai
    ```

5. Start the validator:
    - Without Twitter API key (validated by the master validator):
        ```sh
        python3 -m subnet.cli-sub YOUR_VALI_KEY
        ```

    - With Twitter API key (self-validation):
        ```sh
        export MC_BEARER_TOKEN=YOUR_TWITTER_BEARER_TOKEN
        python3 -m subnet.cli-sub YOUR_VALI_KEY
        ```

## Further Reading

For comprehensive documentation on the Commune AI ecosystem, visit the [Official Commune Page](https://communeai.org/) and its developer documentation. There, you can learn about all subnet details, deployment processes, and more.

---
