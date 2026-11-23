"""用独立的分数参考值核对 M1 概率。"""

from dataclasses import replace
from fractions import Fraction
from typing import Literal, cast
from unittest import TestCase

from deermind.spaces.evaluation.belief import (
    M1_PARAMETERS,
    predict_learning,
    update_observation,
    validate_parameters,
)


class BeliefTests(TestCase):
    def test_quarter_and_negative_sequence(self) -> None:
        # 1/4 与 1/5 的合格作答由上游归入同一分项。
        sequence: tuple[tuple[Literal["positive", "negative"], Fraction, float], ...] = (
            ("positive", Fraction(17, 22), 0.772727),
            ("positive", Fraction(289, 314), 0.920382),
            ("negative", Fraction(289, 414), 0.698068),
            ("positive", Fraction(4913, 5538), 0.887143),
            ("positive", Fraction(83521, 86646), 0.963934),
        )
        current = M1_PARAMETERS.p0
        for verdict, expected, display in sequence:
            with self.subTest(verdict=verdict, expected=expected):
                updated = update_observation(current, verdict, M1_PARAMETERS)
                self.assertAlmostEqual(updated.p_obs, float(expected), places=15)
                self.assertEqual(updated.p_obs, updated.p_current)
                self.assertEqual(round(updated.p_obs, 6), display)
                current = updated.p_current

    def test_teaching_predicts_without_changing_observation(self) -> None:
        observed = update_observation(M1_PARAMETERS.p0, "positive", M1_PARAMETERS)
        for aspect in ("independent", "understanding"):
            forecast = predict_learning(observed.p_current, aspect, True, M1_PARAMETERS)
            self.assertAlmostEqual(forecast, float(Fraction(69, 88)), places=15)
            next_observation = update_observation(forecast, "positive", M1_PARAMETERS)
            self.assertAlmostEqual(next_observation.p_obs, float(Fraction(1173, 1268)), places=15)
        self.assertAlmostEqual(observed.p_obs, float(Fraction(17, 22)), places=15)

    def test_ineligible_or_zero_learning_is_unchanged(self) -> None:
        probability = 0.8999999999999999
        for aspect in ("independent", "understanding", "transfer", "retention"):
            value = predict_learning(probability, aspect, False, M1_PARAMETERS)
            self.assertEqual(value, probability)
        for aspect in ("transfer", "retention"):
            value = predict_learning(probability, aspect, True, M1_PARAMETERS)
            self.assertEqual(value, probability)
        zero = replace(M1_PARAMETERS, learn=0.0)
        self.assertEqual(predict_learning(probability, "independent", True, zero), probability)
        with self.assertRaises(ValueError):
            update_observation(
                probability, cast(Literal["positive", "negative"], "unknown"), M1_PARAMETERS
            )

    def test_invalid_parameters_and_probability(self) -> None:
        for values in (
            replace(M1_PARAMETERS, p0=0.0),
            replace(M1_PARAMETERS, p0=1.0),
            replace(M1_PARAMETERS, slip=0.0),
            replace(M1_PARAMETERS, slip=1.0),
            replace(M1_PARAMETERS, guess=0.0),
            replace(M1_PARAMETERS, slip=0.75, guess=0.25),
            replace(M1_PARAMETERS, learn=-0.01),
            replace(M1_PARAMETERS, learn=1.0),
            replace(M1_PARAMETERS, learn=float("nan")),
            replace(M1_PARAMETERS, guess=float("inf")),
        ):
            with self.subTest(parameters=values), self.assertRaises(ValueError):
                validate_parameters(values)
        for probability in (-0.01, 1.01, float("nan"), float("inf")):
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                update_observation(probability, "positive", M1_PARAMETERS)

    def test_probability_endpoints(self) -> None:
        for verdict in ("positive", "negative"):
            self.assertEqual(update_observation(0.0, verdict, M1_PARAMETERS).p_obs, 0.0)
            self.assertEqual(update_observation(1.0, verdict, M1_PARAMETERS).p_obs, 1.0)
        self.assertEqual(predict_learning(0.0, "independent", True, M1_PARAMETERS), 0.05)
        self.assertEqual(predict_learning(1.0, "understanding", True, M1_PARAMETERS), 1.0)
