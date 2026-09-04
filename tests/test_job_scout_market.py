import asyncio
from pathlib import Path

from nerve_center.config import Settings
from nerve_center.plugins.job_scout.market import GazetteerMarketExpander


def _write_fixture(cache: Path) -> None:
    cache.mkdir(parents=True)
    cache.joinpath("places.txt").write_text(
        "USPS|GEOID|GEOIDFQ|ANSICODE|NAME|LSAD|FUNCSTAT|ALAND|AWATER|ALAND_SQMI|"
        "AWATER_SQMI|INTPTLAT|INTPTLONG\n"
        "NC|3728000|x|x|Greensboro city|25|A|0|0|0|0|36.0726|-79.7920\n"
        "NC|3775000|x|x|Winston-Salem city|25|A|0|0|0|0|36.0999|-80.2442\n"
        "NC|3709060|x|x|Burlington city|25|A|0|0|0|0|36.0957|-79.4378\n",
        encoding="utf-8",
    )
    cache.joinpath("counties.txt").write_text(
        "USPS|GEOID|GEOIDFQ|ANSICODE|NAME|ALAND|AWATER|ALAND_SQMI|AWATER_SQMI|"
        "INTPTLAT|INTPTLONG\n"
        "NC|37081|x|x|Guilford County|0|0|0|0|36.0791|-79.7887\n",
        encoding="utf-8",
    )
    cache.joinpath("cbsa.txt").write_text(
        "CSAFP|GEOID|GEOIDFQ|NAME|CBSA_TYPE|ALAND|AWATER|ALAND_SQMI|AWATER_SQMI|"
        "INTPTLAT|INTPTLONG\n"
        "|24660|x|Greensboro-High Point, NC|Metropolitan Statistical Area|0|0|0|0|"
        "36.0450|-79.8000\n",
        encoding="utf-8",
    )


def test_expands_start_location_with_cached_public_geography(tmp_path: Path) -> None:
    cache = tmp_path / "gazetteer"
    _write_fixture(cache)
    expander = GazetteerMarketExpander(Settings(data_dir=tmp_path / "runtime"), cache_dir=cache)

    aliases = asyncio.run(expander.expand(["Greensboro, NC"], radius_miles=50))
    labels = [item.label for item in aliases]

    assert labels[0] == "Greensboro, NC"
    assert "Burlington, NC" in labels
    assert "Winston-Salem, NC" in labels
    assert "Guilford County, NC" in labels
    assert "Greensboro-High Point, NC" in labels
    assert all(item.provenance.startswith(("configured_", "census_")) for item in aliases)


def test_unknown_location_remains_a_search_alias_without_network(tmp_path: Path) -> None:
    cache = tmp_path / "gazetteer"
    _write_fixture(cache)
    expander = GazetteerMarketExpander(Settings(data_dir=tmp_path / "runtime"), cache_dir=cache)

    aliases = asyncio.run(expander.expand(["Not A Place, NC"]))

    assert [item.label for item in aliases] == ["Not A Place, NC"]
