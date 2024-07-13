from pydantic_settings import BaseSettings

class ValidatorSettings(BaseSettings):
    subnet_name: str = 'market-compass'
    iteration_interval: int = 60  # Set, accordingly to your tempo.
    max_allowed_weights: int = 400  # Query dynamically based on your subnet settings.
