import pytest
import pathlib
import polars as pl
from scripts.profile_ddinter2 import compute_sha256, profile_dataframe

def test_compute_sha256_reproducible(tmp_path):
    """Prueba que el hash sha256 sea reproducible e idéntico para el mismo archivo."""
    file_path = tmp_path / "test.csv"
    file_path.write_text("col1,col2\nval1,val2\n", encoding="utf-8")
    
    hash1 = compute_sha256(file_path)
    hash2 = compute_sha256(file_path)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_profile_dataframe_basic(tmp_path):
    """Prueba métricas básicas de perfilamiento sobre un DataFrame válido."""
    csv_data = (
        "DDInterID_A,Drug_A,DDInterID_B,Drug_B,Level\n"
        "ID1,DrugA,ID2,DrugB,Major\n"
        "ID3,DrugC,ID4,DrugD,Moderate\n"
    )
    file_path = tmp_path / "test_basic.csv"
    file_path.write_text(csv_data, encoding="utf-8")
    
    df = pl.read_csv(file_path)
    schema_inv, quality_metrics, pair_qual = profile_dataframe(df, "test_basic.csv")
    
    # 1. Conteo de filas y esquema
    assert len(schema_inv) == 5
    assert schema_inv[0]["column_name"] == "DDInterID_A"
    
    # 2. Métricas de nulos y vacíos
    assert quality_metrics[0]["null_count"] == 0
    assert quality_metrics[0]["empty_string_count"] == 0
    
    # 3. Métricas de pares
    assert pair_qual["total_rows"] == 2
    assert pair_qual["valid_pairs"] == 2
    assert pair_qual["unique_canonical_pairs"] == 2
    assert pair_qual["duplicate_pairs"] == 0
    assert pair_qual["reverse_pairs"] == 0
    assert pair_qual["auto_interactions"] == 0


def test_profile_dataframe_duplicates_and_reversals():
    """Prueba la detección de duplicados exactos, pares reversos (A+B y B+A) y auto-interacciones (A+A)."""
    df = pl.DataFrame({
        "DDInterID_A": ["1", "2", "1", "3"],
        "Drug_A": ["DrugA", "DrugB", "DrugA", "DrugA"],
        "DDInterID_B": ["2", "1", "2", "3"],
        "Drug_B": ["DrugB", "DrugA", "DrugB", "DrugA"],
        "Level": ["Major", "Major", "Major", "Minor"]
    })
    
    # Explicación de las filas:
    # 1. DrugA + DrugB (Major)
    # 2. DrugB + DrugA (Major) -> Par reverso de la fila 1 (DrugA + DrugB / DrugB + DrugA)
    # 3. DrugA + DrugB (Major) -> Duplicado exacto de la fila 1
    # 4. DrugA + DrugA (Minor) -> Auto-interacción (A+A)
    
    schema_inv, quality_metrics, pair_qual = profile_dataframe(df, "test_dups.csv")
    
    assert pair_qual["total_rows"] == 4
    assert pair_qual["valid_pairs"] == 4
    # Pares canónicos únicos de interés: 
    # {DRUGA, DRUGB} (filas 1, 2, 3) y {DRUGA, DRUGA} (fila 4). Total: 2
    assert pair_qual["unique_canonical_pairs"] == 2
    # Duplicados exactos: la fila 3 ("DrugA", "DrugB") es copia de la fila 1. Total: 1
    assert pair_qual["duplicate_pairs"] == 1
    # Pares reversos únicos: DrugA+DrugB y DrugB+DrugA. Hay 1 par reverso único (DrugA < DrugB). Total: 1
    assert pair_qual["reverse_pairs"] == 1
    # Auto-interacciones: DrugA+DrugA (fila 4). Total: 1
    assert pair_qual["auto_interactions"] == 1


def test_profile_empty_dataframe():
    """Prueba el perfilamiento sobre un DataFrame vacío sin filas."""
    df = pl.DataFrame(
        schema={
            "DDInterID_A": pl.String,
            "Drug_A": pl.String,
            "DDInterID_B": pl.String,
            "Drug_B": pl.String,
            "Level": pl.String
        }
    )
    schema_inv, quality_metrics, pair_qual = profile_dataframe(df, "test_empty.csv")
    assert pair_qual["total_rows"] == 0
    assert pair_qual["valid_pairs"] == 0
    assert pair_qual["unique_canonical_pairs"] == 0
    assert pair_qual["duplicate_pairs"] == 0
    assert pair_qual["reverse_pairs"] == 0
    assert pair_qual["auto_interactions"] == 0


def test_profile_incompatible_schema():
    """Prueba que el perfilamiento no falle catastróficamente ante esquemas incompatibles (columnas ausentes)."""
    df = pl.DataFrame({
        "ID_X": ["X1"],
        "Drug_X": ["DrugX"],
        "ID_Y": ["Y1"],
        "Drug_Y": ["DrugY"]
    })
    schema_inv, quality_metrics, pair_qual = profile_dataframe(df, "test_incompat.csv")
    # Al no tener Drug_A y Drug_B, pair_qual debe quedar vacío
    assert pair_qual == {}
