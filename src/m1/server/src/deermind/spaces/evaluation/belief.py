"""Evaluation 的确定性概率计算。证据资格和防重由调用方核对。"""

from dataclasses import dataclass
from typing import Literal

PARAMETER_REF = "M1-BELIEF-PARAM-01"
ALGORITHM_REF = "M1-BELIEF-ALGORITHM-01"


@dataclass(frozen=True)
class BeliefParameters:
    p0: float
    slip: float
    guess: float
    learn: float


M1_PARAMETERS = BeliefParameters(p0=0.50, slip=0.15, guess=0.25, learn=0.05)


@dataclass(frozen=True)
class ObservationUpdate:
    p_obs: float
    p_current: float


def validate_parameters(parameters: BeliefParameters) -> None:
    p0, slip, guess, learn = parameters.p0, parameters.slip, parameters.guess, parameters.learn
    valid_measurement = 0 < slip < 1 and 0 < guess < 1 and 1 - slip > guess
    if not (0 < p0 < 1 and valid_measurement and 0 <= learn < 1):
        raise ValueError("Invalid belief parameters")


def _validate_probability(probability: float) -> None:
    if not 0 <= probability <= 1:
        raise ValueError("Invalid belief probability")


def update_observation(
    p_current: float, verdict: Literal["positive", "negative"], parameters: BeliefParameters
) -> ObservationUpdate:
    """把一条已确认符合资格的正证或反证更新为观测后验。"""
    validate_parameters(parameters)
    _validate_probability(p_current)
    if verdict == "positive":
        known, unknown = 1 - parameters.slip, parameters.guess
    elif verdict == "negative":
        known, unknown = parameters.slip, 1 - parameters.guess
    else:
        raise ValueError("Observation requires a positive or negative verdict")
    numerator = p_current * known
    denominator = numerator + (1 - p_current) * unknown
    if denominator <= 0:
        raise ValueError("Invalid observation denominator")
    posterior = numerator / denominator
    _validate_probability(posterior)
    return ObservationUpdate(p_obs=posterior, p_current=posterior)


def predict_learning(
    p_current: float, aspect: str, qualified_opportunity: bool, parameters: BeliefParameters
) -> float:
    """只返回新的预测值，保留原观测概率和观测时间。"""
    validate_parameters(parameters)
    _validate_probability(p_current)
    if not qualified_opportunity or aspect not in {"independent", "understanding"}:
        return p_current
    forecast = p_current + parameters.learn * (1 - p_current)
    _validate_probability(forecast)
    return forecast
