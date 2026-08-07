from backend.app.services.ddinter_csv_provider import DDInterCsvProvider


def test_ddinter_provider_deduplicates_and_uses_highest_severity(tmp_path):
    data_dir = tmp_path / "ddinter"
    data_dir.mkdir()
    header = "DDInterID_A,Drug_A,DDInterID_B,Drug_B,Level\n"
    (data_dir / "ddinter_downloads_code_A.csv").write_text(
        header + "DDInter1,Drug One,DDInter2,Drug Two,Minor\n",
        encoding="utf-8",
    )
    (data_dir / "ddinter_downloads_code_B.csv").write_text(
        header + "DDInter1,Drug One,DDInter2,Drug Two,Major\n",
        encoding="utf-8",
    )
    alias_file = tmp_path / "aliases.csv"
    alias_file.write_text(
        "local_active_ingredient,ddinter_drug_name,status\n"
        "FARMACO UNO,Drug One,provisional\n",
        encoding="utf-8",
    )

    provider = DDInterCsvProvider(data_dir=data_dir, alias_file=alias_file)
    results = provider.find_interactions(["FARMACO UNO", "Drug Two"])

    assert len(results) == 1
    assert results[0]["severity"] == "alta"
    assert results[0]["analysis_system"] == "ddinter"
    assert results[0]["implicated_medications"] == ["DRUG TWO", "FARMACO UNO"]
    assert len(results[0]["catalog_files"]) == 2


def test_ddinter_provider_excludes_unknown_by_default(tmp_path):
    data_dir = tmp_path / "ddinter"
    data_dir.mkdir()
    (data_dir / "ddinter_downloads_code_A.csv").write_text(
        "DDInterID_A,Drug_A,DDInterID_B,Drug_B,Level\n"
        "DDInter1,Drug One,DDInter2,Drug Two,Unknown\n",
        encoding="utf-8",
    )

    provider = DDInterCsvProvider(data_dir=data_dir, alias_file=tmp_path / "none.csv")
    assert provider.find_interactions(["Drug One", "Drug Two"]) == []


def test_local_ddinter_catalog_is_used_for_real_pair():
    provider = DDInterCsvProvider()
    results = provider.find_interactions(["Naltrexone", "Abacavir"])

    assert len(results) == 1
    assert results[0]["severity"] == "moderada"
    assert results[0]["is_demo"] is False
