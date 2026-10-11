from copy import deepcopy

from Backend.AI.app.validators.metadata_spec_validator import (
    MetadataSpecification,
)


class MetadataSpecStore:
    """Development-only, single-process, in-memory artifact store."""

    def __init__(self):
        self._specifications: dict[str, MetadataSpecification] = {}
        self._packages: dict[str, dict] = {}
        self.on_save = None

    def save(
        self,
        specification: MetadataSpecification,
    ) -> MetadataSpecification:
        self._specifications[specification.planId] = specification
        return specification

    def get(
        self,
        plan_id: str,
    ) -> MetadataSpecification | None:
        return self._specifications.get(plan_id)

    def list(self) -> list[MetadataSpecification]:
        return list(self._specifications.values())

    def delete(self, plan_id: str) -> None:
        self._packages.pop(plan_id, None)
        self._specifications.pop(plan_id, None)

    def save_package(self, package: dict) -> dict:
        if self.on_save is not None:
            self.on_save(deepcopy(package))
        self._packages[package["plan"]["id"]] = deepcopy(package)
        return deepcopy(package)

    def get_package(self, plan_id: str) -> dict | None:
        return deepcopy(self._packages.get(plan_id))