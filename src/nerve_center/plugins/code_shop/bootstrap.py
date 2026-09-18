"""Code Shop composition adapter for the Nerve Center manager."""

from dataclasses import dataclass

from fastapi import FastAPI

from nerve_center.code_shop.api import register_code_shop_routes
from nerve_center.code_shop.github import GitHubRepositoryConnector
from nerve_center.code_shop.service import CodeShopService
from nerve_center.config import Settings
from nerve_center.domain.module import ModuleManifest
from nerve_center.persistence.code_shop import CodeShopRepository
from nerve_center.persistence.database import Database
from nerve_center.plugins.code_shop.manifest import code_shop_manifest
from nerve_center.plugins.code_shop.runtime import CodeShopOperationBridge


@dataclass(frozen=True, slots=True)
class CodeShopModulePackage:
    manifest: ModuleManifest
    operation_bridge: CodeShopOperationBridge
    service: CodeShopService


def install_code_shop(
    application: FastAPI,
    database: Database,
    settings: Settings,
    connector: GitHubRepositoryConnector,
) -> CodeShopModulePackage:
    service = CodeShopService(
        CodeShopRepository(database),
        connector,
        settings.code_shop_checkout_roots,
    )
    register_code_shop_routes(application, service)
    application.state.code_shop = service
    return CodeShopModulePackage(
        manifest=code_shop_manifest(),
        operation_bridge=CodeShopOperationBridge(service),
        service=service,
    )
