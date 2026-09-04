"""Job Scout composition adapter for the Nerve Center manager."""

from dataclasses import dataclass

from fastapi import FastAPI

from nerve_center.applications.api import register_application_routes
from nerve_center.config import Settings
from nerve_center.discovery.api import register_discovery_routes
from nerve_center.discovery.service import DiscoveryService
from nerve_center.domain.module import ModuleManifest
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.plugins.job_scout.configuration import (
    register_job_scout_configuration_routes,
)
from nerve_center.plugins.job_scout.discovery_learning import JobScoutDiscoveryRepository
from nerve_center.plugins.job_scout.discovery_loop import JobScoutDiscoveryLoop
from nerve_center.plugins.job_scout.manifest import job_scout_manifest
from nerve_center.plugins.job_scout.runtime import JobScoutOperationBridge
from nerve_center.plugins.job_scout.uploads import register_job_scout_upload_route
from nerve_center.profile.api import register_profile_routes
from nerve_center.providers.base import StructuredProvider
from nerve_center.scoring.api import register_scoring_routes


@dataclass(frozen=True, slots=True)
class JobScoutModulePackage:
    manifest: ModuleManifest
    operation_bridge: JobScoutOperationBridge


def install_job_scout(
    application: FastAPI,
    database: Database,
    settings: Settings,
    provider: StructuredProvider | None,
) -> JobScoutModulePackage:
    company_repository = CompanyRepository(database)
    source_repository = DiscoverySourceRepository(database)
    job_repository = JobOpeningRepository(database)
    learning_repository = JobScoutDiscoveryRepository(database)
    discovery_service = DiscoveryService(
        company_repository,
        source_repository,
        job_repository,
    )
    register_profile_routes(application, database, settings, provider)
    register_discovery_routes(application, database, settings, discovery_service)
    scoring_service = register_scoring_routes(application, database, settings, provider)
    coordinator = register_job_scout_configuration_routes(
        application,
        database,
        settings,
        provider,
        discovery_service,
        company_repository,
        source_repository,
        job_repository,
    )
    discovery_loop = JobScoutDiscoveryLoop(
        settings,
        coordinator,
        discovery_service,
        company_repository,
        source_repository,
        job_repository,
        learning_repository,
    )
    register_application_routes(
        application,
        database,
        scoring_service=scoring_service,
        configuration_store=coordinator.store,
    )
    register_job_scout_upload_route(application, settings)
    return JobScoutModulePackage(
        manifest=job_scout_manifest(),
        operation_bridge=JobScoutOperationBridge(
            discovery_service,
            source_repository,
            coordinator,
            learning_repository,
            discovery_loop,
        ),
    )
