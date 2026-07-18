"""Base Pydantic configuration used by public application contracts."""

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Reject unknown fields so agent and API payload drift fails closed."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        validate_default=True,
    )
