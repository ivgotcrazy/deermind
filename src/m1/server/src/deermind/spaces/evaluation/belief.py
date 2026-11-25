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
    # 测量参数：失误率 slip 与猜测率 guess 均在 (0,1)，且失误率须低于猜测率。
    valid_measurement = 0 < slip < 1 and 0 < guess < 1 and 1 - slip > guess
    # 先验 p0 与学习率 learn 也须落在合法区间，否则参数不可用。
    if not (0 < p0 < 1 and valid_measurement and 0 <= learn < 1):
        raise ValueError("Invalid belief parameters")


def _validate_probability(probability: float) -> None:
    # 概率必须在 [0,1] 闭区间内。
    if not 0 <= probability <= 1:
        raise ValueError("Invalid belief probability")


def update_observation(
    p_current: float, verdict: Literal["positive", "negative"], parameters: BeliefParameters
) -> ObservationUpdate:
    """把一条已确认符合资格的正证或反证更新为观测后验。"""
    validate_parameters(parameters)
    _validate_probability(p_current)
    # 正证：已知掌握时答对概率 1-slip，未掌握时蒙对概率 guess。
    if verdict == "positive":
        known, unknown = 1 - parameters.slip, parameters.guess
    # 反证：已知掌握时失误概率 slip，未掌握时蒙错概率 1-guess。
    elif verdict == "negative":
        known, unknown = parameters.slip, 1 - parameters.guess
    # 其余结论取值不构成有效观测。
    else:
        raise ValueError("Observation requires a positive or negative verdict")
    numerator = p_current * known
    denominator = numerator + (1 - p_current) * unknown
    # 分母为 0 时后验不可计算，判观测无效。
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
    # 机会未获资格，或方面不在可学习范围（独立/理解）内，预测概率保持不变。
    if not qualified_opportunity or aspect not in {"independent", "understanding"}:
        return p_current
    forecast = p_current + parameters.learn * (1 - p_current)
    _validate_probability(forecast)
    return forecast
