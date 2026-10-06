"""FastAPI routes for experiment metadata management."""

import importlib

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from database.connection import DatabaseError
from database.experiment_repository import ExperimentRepository


experiment_module = importlib.import_module("digital-twin.experiment")
Experiment = experiment_module.Experiment
ExperimentError = experiment_module.ExperimentError
ExperimentStatus = experiment_module.ExperimentStatus
ScenarioParameters = experiment_module.ScenarioParameters
ScenarioType = experiment_module.ScenarioType


router = APIRouter(tags=["experiments"])


class ScenarioParametersRequest(BaseModel):
    multiplier: float | None = None
    instance_name: str | None = None
    additional_instances: int | None = None


class ExperimentCreateRequest(BaseModel):
    experiment_id: str
    name: str
    scenario_type: ScenarioType
    scenario_parameters: ScenarioParametersRequest


class ScenarioParametersResponse(BaseModel):
    multiplier: float | None
    instance_name: str | None
    additional_instances: int | None


class ExperimentResponse(BaseModel):
    experiment_id: str
    name: str
    scenario_type: ScenarioType
    status: ExperimentStatus
    scenario_parameters: ScenarioParametersResponse


def get_experiment_repository() -> ExperimentRepository:
    """Provide a repository for one API request."""
    return ExperimentRepository()


def _to_experiment(request: ExperimentCreateRequest) -> object:
    parameters = ScenarioParameters(
        multiplier=request.scenario_parameters.multiplier,
        instance_name=request.scenario_parameters.instance_name,
        additional_instances=request.scenario_parameters.additional_instances,
    )
    parameters.validate(request.scenario_type)
    return Experiment(
        experiment_id=request.experiment_id,
        name=request.name,
        scenario_type=request.scenario_type,
        scenario_parameters=parameters,
    )


def _to_response(experiment: object) -> ExperimentResponse:
    parameters = experiment.scenario_parameters
    return ExperimentResponse(
        experiment_id=experiment.experiment_id,
        name=experiment.name,
        scenario_type=experiment.scenario_type,
        status=experiment.status,
        scenario_parameters=ScenarioParametersResponse(
            multiplier=parameters.multiplier,
            instance_name=parameters.instance_name,
            additional_instances=parameters.additional_instances,
        ),
    )


@router.post(
    "/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_experiment(
    request: ExperimentCreateRequest,
    repository: ExperimentRepository = Depends(get_experiment_repository),
) -> ExperimentResponse:
    try:
        experiment = _to_experiment(request)
    except ExperimentError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        repository.create(experiment)
    except DatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="experiment database unavailable",
        ) from error
    return _to_response(experiment)


@router.get("/experiments", response_model=list[ExperimentResponse])
def list_experiments(
    repository: ExperimentRepository = Depends(get_experiment_repository),
) -> list[ExperimentResponse]:
    try:
        experiments = repository.list_all()
    except DatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="experiment database unavailable",
        ) from error
    return [_to_response(experiment) for experiment in experiments]


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(
    experiment_id: str,
    repository: ExperimentRepository = Depends(get_experiment_repository),
) -> ExperimentResponse:
    try:
        experiment = repository.get_by_id(experiment_id)
    except DatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="experiment database unavailable",
        ) from error
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="experiment not found")
    return _to_response(experiment)