from ra2ce.analyses.indirect.traffic_analysis.accumulated_traffic_dataclass import (
    AccumulatedTaffic,
)
import pytest


@pytest.fixture
def valid_accumulated_traffic() -> AccumulatedTaffic:
    yield AccumulatedTaffic(1, 2, 3)


multiplicate_cases = [
    pytest.param(
        AccumulatedTaffic(2, 2, 2),
        AccumulatedTaffic(2, 4, 6),
        id="With an AccumulatedTraffic object.",
    ),
    pytest.param(3.0, AccumulatedTaffic(3, 6, 9), id="With a float."),
    pytest.param(4, AccumulatedTaffic(4, 8, 12), id="With an int."),
]
addition_cases = [
    pytest.param(
        AccumulatedTaffic(2, 2, 2),
        AccumulatedTaffic(3, 4, 5),
        id="With an AccumulatedTraffic object.",
    ),
    pytest.param(3.0, AccumulatedTaffic(4, 5, 6), id="With a float."),
    pytest.param(4, AccumulatedTaffic(5, 6, 7), id="With an int."),
]


class TestAccumulatedTrafficDataclass:
    def test_multiply_wrong_type_raises_error(self):
        with pytest.raises(NotImplementedError) as exc_err:
            AccumulatedTaffic() * "Lorem ipsum"
        assert (
            str(exc_err.value)
            == "It is not possible to multiply AccumulatedTaffic with a value of type str."
        )

    def test_addition_wrong_type_raises_error(self):
        with pytest.raises(NotImplementedError) as exc_err:
            AccumulatedTaffic() + "Lorem ipsum"
        assert (
            str(exc_err.value)
            == "It is not possible to sum AccumulatedTaffic with a value of type str."
        )

    @pytest.mark.parametrize("right_value, expected_result", multiplicate_cases)
    def test_multiply_values(
        self,
        valid_accumulated_traffic: AccumulatedTaffic,
        right_value: AccumulatedTaffic,
        expected_result: AccumulatedTaffic,
    ):
        # 2. Run test.
        _result = valid_accumulated_traffic * right_value

        # 3. Verify expectation.
        assert _result != valid_accumulated_traffic
        assert _result != right_value
        assert _result.regular == expected_result.regular
        assert _result.egalitarian == expected_result.egalitarian
        assert _result.prioritarian == expected_result.prioritarian

    @pytest.mark.parametrize("right_value, expected_result", multiplicate_cases)
    def test_multiply_values_compressed_operator(
        self,
        valid_accumulated_traffic: AccumulatedTaffic,
        right_value: AccumulatedTaffic,
        expected_result: AccumulatedTaffic,
    ):
        # 2. Run test.
        valid_accumulated_traffic *= right_value

        # 3. Verify expectation.
        assert valid_accumulated_traffic != right_value
        assert valid_accumulated_traffic.regular == expected_result.regular
        assert valid_accumulated_traffic.egalitarian == expected_result.egalitarian
        assert valid_accumulated_traffic.prioritarian == expected_result.prioritarian

    @pytest.mark.parametrize("right_value, expected_result", addition_cases)
    def test_add_values(
        self,
        valid_accumulated_traffic: AccumulatedTaffic,
        right_value: AccumulatedTaffic,
        expected_result: AccumulatedTaffic,
    ):
        # 2. Run test.
        _result = valid_accumulated_traffic + right_value

        # 3. Verify expectation.
        assert _result != valid_accumulated_traffic
        assert _result != right_value
        assert _result.regular == expected_result.regular
        assert _result.egalitarian == expected_result.egalitarian
        assert _result.prioritarian == expected_result.prioritarian

    @pytest.mark.parametrize("right_value, expected_result", addition_cases)
    def test_add_values_compressed(
        self,
        valid_accumulated_traffic: AccumulatedTaffic,
        right_value: AccumulatedTaffic,
        expected_result: AccumulatedTaffic,
    ):
        # 2. Run test.
        valid_accumulated_traffic += right_value

        # 3. Verify expectation.
        assert valid_accumulated_traffic != right_value
        assert valid_accumulated_traffic.regular == expected_result.regular
        assert valid_accumulated_traffic.egalitarian == expected_result.egalitarian
        assert valid_accumulated_traffic.prioritarian == expected_result.prioritarian
