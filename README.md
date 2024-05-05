# Market Compass Subnet code based on Commune Subnet Template

Market Compass Subnet built on top of [CommuneX](https://github.com/agicommies/communex).
Learn how to structure, build and deploy a subnet on [Commune AI](https://communeai.org/)!

## Environment Miner Variables

MC_BEARER_TOKEN - Bearer token for twitter pro api.
`export MC_BEARER_TOKEN=AAA...`

`export MC_SUBNET_API_X_API_KEY=`

## Environment Validator Variables
MC_SUBNET_API_X_API_KEY - MarketCompass API key, please contact via discord-ticket to get a new one [Subnet 17 Discord Server](https://discord.gg/9KXf3BMCJA).
`export MC_SUBNET_API_X_API_KEY=`

In request please provide: `module_id` `module_ip` `is_validator` `discord_user`

MC_SUBNET_API_URL - URL to current version of the used api
`export MC_SUBNET_API_URL=https://api3.subnet.marketcompass.ai`

## Dependencies
The whole subnet is built on top of the [CommuneX library / SDK](https://github.com/agicommies/communex).
Which is truly the only essential dependency.
You can find the whole dependency list we used in the [requirements.txt](requirements.txt) file.

```txt
communex
typer
uvicorn
keylimiter
pydantic-settings
```

## Miner

From the root of your project, you can just call **comx module serve**. For example:

```sh
comx module serve subnet.miner.model.Miner <name-of-your-com-key> --subnets-whitelist 17 --ip 0.0.0.0 --port 8000
```

To register the miner use:
```sh
comx module register <name-of-your-miner> <name-of-your-com-key> --ip <your-ip-of-the-server> --port 8000 --netuid 17  
```

## Validator

To run the validator, just call the file in which you are executing `validator.validate_loop()`. For example:

```sh
python3 -m market-compass-subnet.subnet.cli <name-of-your-com-key>
```

To register the validator use:
```sh
comx module register market-compass::<your-vali-name> <name-of-your-com-key> --netuid 17  
```

## Further reading
For full documentation of the Commune AI ecosystem, please visit the [Official Commune Page](https://communeai.org/),
and it's developer documentation. There you can learn about all subnet details, deployment, and more!
