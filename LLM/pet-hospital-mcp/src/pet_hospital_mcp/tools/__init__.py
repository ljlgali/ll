"""Tool package. Each module registers one MCP tool."""

from pet_hospital_mcp.tools.list_pets import (
    Charge,
    ListPetsInput,
    ListPetsSuccess,
    MedicalRecord,
    Pet,
    register_list_pets,
)

__all__ = [
    "Charge",
    "ListPetsInput",
    "ListPetsSuccess",
    "MedicalRecord",
    "Pet",
    "register_list_pets",
]
